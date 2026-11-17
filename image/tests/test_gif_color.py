"""Sixteen-colour GIF decoding for the Tandy/PCjr display.

Pillow writes the fixtures; the expected output comes from an independent
model here (palette distances, first-sample reduction), never from the
decoder itself. A second, sanitizer-built driver replays every truncation,
random mutations and every possible allocation failure.
"""
import ctypes as C
import io
import pathlib
import random
import subprocess
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
RGBI = [(0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),(170,170,170),
        (85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255)]
BAYER = [0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5]


class Gif(C.Structure):
    _fields_ = [('width', C.c_uint), ('height', C.c_uint), ('stride', C.c_uint),
                ('pixels', C.POINTER(C.c_ubyte)), ('opacity', C.POINTER(C.c_ubyte)),
                ('depth', C.c_ubyte)]


def gif(image, **options):
    data = io.BytesIO()
    image.save(data, 'GIF', **options)
    return data.getvalue()


def indexed(width, height, palette, pixel):
    image = Image.new('P', (width, height))
    flat = [channel for color in palette for channel in color]
    image.putpalette(flat + [0]*(768-len(flat)))
    image.putdata([pixel(x, y) for y in range(height) for x in range(width)])
    return image


DRIVER = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static long budget = -1, live;
static void *test_malloc(size_t n) { if (budget == 0) return 0; if (budget > 0) --budget; ++live; return malloc(n); }
static void test_free(void *p) { if (p) --live; free(p); }
#define malloc test_malloc
#define free test_free
#include "GIF_SOURCE"
#undef malloc
#undef free
static unsigned long state = 12345;
static unsigned next(void) { state = state * 1103515245UL + 12345UL; return (unsigned)(state >> 16) & 0x7fff; }
static void attempt(const unsigned char *data, unsigned length, unsigned w, unsigned h, int must) {
    struct ew_gif image;
    unsigned char *copy = malloc(length ? length : 1);   /* exact size: overreads trip ASan */
    int result;
    memcpy(copy, data, length);
    result = ew_gif_decode_color(copy, length, &image, w, h);
    if (result == EW_GIF_OK) {
        unsigned x, y, sum = 0;
        if (!image.pixels || image.depth != 4 || !image.width || !image.height ||
            image.width > w || image.height > h || image.stride != (image.width + 1) / 2) abort();
        for (y = 0; y < image.height; ++y) for (x = 0; x < image.stride; ++x)
            sum += image.pixels[y * image.stride + x];
        if (image.opacity) for (y = 0; y < image.height; ++y) for (x = 0; x < (image.width + 7) / 8; ++x)
            sum += image.opacity[y * ((image.width + 7) / 8) + x];
        (void)sum;
        ew_gif_free(&image);
    } else if (image.pixels || image.opacity || image.width) abort();
    if (must >= 0 && result != must) { fprintf(stderr, "result %d, wanted %d\n", result, must); abort(); }
    if (live) { fprintf(stderr, "%ld allocations leaked\n", live); abort(); }
    free(copy);
}
int main(int argc, char **argv) {
    static unsigned char data[70000], work[70000];
    unsigned length, i, n;
    FILE *file = fopen(argv[1], "rb");
    if (argc < 2 || !file) return 2;
    length = fread(data, 1, sizeof(data), file); fclose(file);
    attempt(data, length, 304, 200, EW_GIF_OK);
    attempt(data, length, 1, 1, EW_GIF_OK);
    attempt(data, length, 640, 480, EW_GIF_OK);
    for (i = 0; i < length; ++i) attempt(data, i, 152, 100, -1);          /* every truncation */
    for (n = 0; n < 4000; ++n) {                                          /* seeded mutations */
        unsigned flips = 1 + next() % 4;
        memcpy(work, data, length);
        while (flips--) work[next() % length] ^= (unsigned char)(1 << (next() & 7));
        attempt(work, length, 16 + next() % 300, 8 + next() % 200, -1);
    }
    for (budget = 0; budget < 4; ++budget) {                              /* nth allocation fails */
        long before = budget;
        struct ew_gif image;
        int result = ew_gif_decode_color(data, length, &image, 304, 200);
        if (result == EW_GIF_OK) { ew_gif_free(&image); budget = before; break; }
        if (result != EW_GIF_NO_MEMORY || image.pixels || live) abort();
        budget = before;
    }
    if (budget == 0 || budget == 4) abort();    /* at least one failure was exercised, then success */
    budget = -1;
    puts("ok");
    return 0;
}
'''


class ColorGif(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-gif-color-')
        root = pathlib.Path(cls.tmp.name)
        subprocess.run(['cc', '-shared', '-fPIC', '-O1', '-Wall', '-Wextra', '-Werror',
                        str(ROOT/'image/gif.c'), '-o', str(root/'gif.so')], check=True, capture_output=True)
        cls.lib = C.CDLL(str(root/'gif.so'))
        (root/'driver.c').write_text(DRIVER.replace('GIF_SOURCE', str(ROOT/'image/gif.c')))
        subprocess.run(['cc', '-g', '-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                        '-Wall', '-Wextra', str(root/'driver.c'), '-o', str(root/'driver')],
                       check=True, capture_output=True)
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decode(self, data, width=304, height=200, expect=0):
        image = Gif()
        result = self.lib.ew_gif_decode_color(data, len(data), C.byref(image), width, height)
        self.assertEqual(result, expect)
        if result:
            self.assertFalse(image.pixels)
            return None
        self.assertEqual(image.depth, 4)
        self.assertEqual(image.stride, (image.width+1)//2)
        pixels = [[(image.pixels[y*image.stride + x//2] & 15) if x & 1 else
                   image.pixels[y*image.stride + x//2] >> 4 for x in range(image.width)]
                  for y in range(image.height)]
        opacity = None
        if image.opacity:
            stride = (image.width+7)//8
            opacity = [[bool(image.opacity[y*stride + x//8] & (0x80 >> (x & 7)))
                        for x in range(image.width)] for y in range(image.height)]
        self.lib.ew_gif_free(C.byref(image))
        return pixels, opacity

    def test_exact_palette_colors_are_never_dithered(self):
        image = indexed(64, 32, RGBI, lambda x, y: (x//4 + y) % 16)
        pixels, opacity = self.decode(gif(image))
        self.assertIsNone(opacity)
        for y in range(32):
            for x in range(64):
                self.assertEqual(pixels[y][x], (x//4 + y) % 16, (x, y))

    def test_interlaced_matches_sequential_at_full_and_reduced_size(self):
        rng = random.Random(5)
        palette = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(64)]
        image = indexed(200, 123, palette, lambda x, y: (x*3 + y*5 + (x*y) % 7) % 64)
        for limits in ((304, 200), (120, 200), (304, 50), (33, 17)):
            plain = self.decode(gif(image), *limits)
            laced = self.decode(gif(image, interlace=True), *limits)
            self.assertEqual(plain, laced, limits)

    def test_transparency_plane_follows_the_transparent_index(self):
        image = indexed(37, 19, RGBI, lambda x, y: 3 if (x + y) % 3 == 0 else (x % 16 if x % 16 != 3 else 4))
        pixels, opacity = self.decode(gif(image, transparency=3))
        self.assertIsNotNone(opacity)
        for y in range(19):
            for x in range(37):
                clear = (x + y) % 3 == 0
                self.assertEqual(opacity[y][x], not clear, (x, y))
                if not clear:
                    self.assertEqual(pixels[y][x], x % 16 if x % 16 != 3 else 4)

    def test_reduction_keeps_proportions_and_the_first_sample(self):
        image = indexed(640, 480, RGBI, lambda x, y: (x//40) % 16 if (y//60) % 2 == 0 else 15 - (x//40) % 16)
        pixels, _ = self.decode(gif(image), 304, 200)
        self.assertEqual((len(pixels[0]), len(pixels)), (266, 200))
        first_x = {}; first_y = {}
        for x in range(640): first_x.setdefault(x*266//640, x)
        for y in range(480): first_y.setdefault(y*200//480, y)
        for y in range(200):
            for x in range(266):
                self.assertEqual(pixels[y][x], image.getpixel((first_x[x], first_y[y])), (x, y))
        tall, _ = self.decode(gif(indexed(10, 400, RGBI, lambda x, y: y % 16)), 304, 200)
        self.assertEqual((len(tall[0]), len(tall)), (5, 200))
        tiny, _ = self.decode(gif(indexed(640, 2, RGBI, lambda x, y: 5)), 304, 200)
        self.assertEqual((len(tiny[0]), len(tiny)), (304, 1))

    def test_in_between_colors_dither_between_the_two_nearest(self):
        def weight(a, b):
            return 2*((a[0]>>2)-(b[0]>>2))**2 + 4*((a[1]>>2)-(b[1]>>2))**2 + ((a[2]>>2)-(b[2]>>2))**2
        for color in ((140,140,140), (255,128,0), (0,0,96), (200,200,255), (90,160,60), (255,255,255), (10,10,10)):
            image = indexed(32, 32, [color], lambda x, y: 0)
            pixels, _ = self.decode(gif(image))
            used = {}
            for y in range(32):
                for x in range(32):
                    used[pixels[y][x]] = used.get(pixels[y][x], 0) + 1
            self.assertLessEqual(len(used), 2, color)
            main = min(range(16), key=lambda i: weight(RGBI[i], color))
            self.assertGreaterEqual(used.get(main, 0), 512, color)   # never the minority
            if len(used) == 2:
                other = next(c for c in used if c != main)
                # The blend must be closer to the request than the main colour alone.
                share = used[other]/1024.0
                blend = tuple(RGBI[main][i]*(1-share) + RGBI[other][i]*share for i in range(3))
                self.assertLess(sum((blend[i]-color[i])**2 for i in range(3)),
                                sum((RGBI[main][i]-color[i])**2 for i in range(3)), color)
                # Ordered pattern: the partner sits exactly where the 4x4 matrix says.
                level = used[other]*16//1024
                for y in range(8):
                    for x in range(8):
                        self.assertEqual(pixels[y][x] == other, BAYER[(y & 3)*4 + (x & 3)] < level)

    def test_limits_and_bad_headers_are_rejected_without_output(self):
        good = gif(indexed(8, 8, RGBI, lambda x, y: 1))
        self.decode(good, 0, 10, expect=4)
        self.decode(good, 641, 10, expect=4)
        self.decode(b'GIF89a', expect=3)
        self.decode(b'NOTAGIF89a' + bytes(20), expect=1)
        self.decode(gif(indexed(641, 2, RGBI, lambda x, y: 1)), expect=2)

    def test_malformed_input_and_allocation_failure_under_sanitizers(self):
        rng = random.Random(9)
        palette = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(256)]
        cases = {
            'plain': gif(indexed(97, 61, palette, lambda x, y: (x*7 + y*13) % 256)),
            'laced': gif(indexed(64, 64, palette, lambda x, y: (x ^ y) % 256), interlace=True),
            'clear': gif(indexed(50, 30, RGBI, lambda x, y: (x + y) % 16), transparency=2),
            'large': gif(indexed(640, 480, RGBI, lambda x, y: (x//8 + y//8) % 16)),
        }
        for name, data in cases.items():
            path = self.root/(name + '.gif')
            path.write_bytes(data)
            done = subprocess.run([str(self.root/'driver'), str(path)], capture_output=True, text=True)
            self.assertEqual((done.returncode, done.stdout.strip()), (0, 'ok'), name + ': ' + done.stderr[-600:])


if __name__ == '__main__':
    unittest.main()
