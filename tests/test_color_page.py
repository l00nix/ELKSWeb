"""Colour display above the raster: HTML colours, 320-column layout, the
image layer's packed-row drawing and its bounded image cache.

The image half compiles the production images.c and GIF decoder and records
what reaches ew_row4; expected pixels are rebuilt here from the stored image
with plain floor scaling. The layout half runs the production parser with the
colour display selected and compares it with the monochrome parse.
"""
import ctypes as C
import io
import pathlib
import random
import subprocess
import tempfile
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
RGBI = [(0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),(170,170,170),
        (85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255)]

SHIM = r'''
#include <stdlib.h>
#include <string.h>
#include "IMAGES_SOURCE"
struct ew_document ew_doc;
int ew_screen_height=200,ew_pixel_aspect=1,ew_screen_width=320,ew_color=1;
uint32_t ew_source_length;
static unsigned char frame[320*200];
static int clip_right=312;
unsigned bad_rows;
void *ew_far_alloc(unsigned long n) { return malloc(n); }
void ew_far_free(void *p) { free(p); }
void ew_copy_to_far(void *d,const void *s,unsigned n) { memcpy(d,s,n); }
void ew_copy_from_far(char *d,const char *s,unsigned n) { if(n) { strncpy(d,s,n-1); d[n-1]=0; } }
unsigned char ew_source_byte(uint32_t n) { (void)n; return 0; }
const char *ew_source_error(void) { return ""; }
int32_t ew_fetch_to_fd(const char*u,int f,uint32_t c,char*v,char*e,unsigned n) {
  (void)u;(void)f;(void)c;(void)v;(void)e;(void)n;return -1; }
void ew_rect(int x,int y,int w,int h,int c) {(void)x;(void)y;(void)w;(void)h;(void)c;}
void ew_glyph(int x,int y,unsigned char c,int f,int b) {(void)x;(void)y;(void)c;(void)f;(void)b;}
int ew_body_char_width(unsigned char c,int bold) {(void)c;(void)bold;return 8;}
void ew_body_draw(int x,int y,unsigned char c,int f,int b,int bold,int italic)
{(void)x;(void)y;(void)c;(void)f;(void)b;(void)bold;(void)italic;}
void ew_pixel(int x,int y,int color) {(void)x;(void)y;(void)color; ++bad_rows;}
/* The driver contract: x,y on screen, row starts at nibble x&1. */
void ew_row4(int x,int y,const unsigned char *line,const unsigned char *mask,int width) {
  int i;
  if (x<0 || y<0 || y>=200 || width<0 || x+width>320) { ++bad_rows; return; }
  for (i=0;i<width && x+i<clip_right;++i) {
    int n=i+(x&1);
    if (mask && !(mask[i>>3]&(0x80>>(i&7)))) continue;
    frame[y*320+x+i]=n&1 ? line[n>>1]&15 : line[n>>1]>>4;
  }
}
int color_load(unsigned slot,const unsigned char *data,unsigned size) {
  int result=decode(data,size,&images[slot]);
  if (!result && slot>=image_count) image_count=slot+1;
  return result;
}
unsigned color_width(unsigned slot) { return images[slot].width; }
unsigned color_height(unsigned slot) { return images[slot].height; }
unsigned long color_total(void) { return color_bytes; }
int color_stored(unsigned slot,unsigned x,unsigned y) {
  struct ew_gif *g=&images[slot];
  unsigned char b=g->pixels[y*g->stride+x/2];
  if (g->opacity && !(g->opacity[y*((g->width+7)/8)+x/8]&(0x80>>(x&7)))) return -1;
  return x&1 ? b&15 : b>>4;
}
unsigned char *color_draw(unsigned width,unsigned height,int x,int y,int top,int bottom,int right) {
  struct ew_run r;
  memset(&r,0,sizeof(r)); r.kind=EW_RUN_IMAGE; r.n=width; r.w=height;
  memset(frame,0xee,sizeof(frame)); clip_right=right;
  ew_image_draw(&r,x,y,top,bottom,0);
  return frame;
}
'''


def gif(image, **options):
    data = io.BytesIO(); image.save(data, 'GIF', **options); return data.getvalue()


def indexed(width, height, pixel):
    image = Image.new('P', (width, height))
    image.putpalette([c for rgb in RGBI for c in rgb] + [0]*(768-48))
    image.putdata([pixel(x, y) for y in range(height) for x in range(width)])
    return image


class ColorImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-color-images-')
        root = pathlib.Path(cls.tmp.name)
        (root/'shim.c').write_text(SHIM.replace('IMAGES_SOURCE', str(ROOT/'src/images.c')))
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-O1',
                        '-DEW_HOST_TEST', '-I'+str(ROOT/'src'), '-I'+str(ROOT/'platform'),
                        str(root/'shim.c'), str(ROOT/'image/gif.c'), str(ROOT/'image/dimensions.c'),
                        '-o', str(root/'images.so')], check=True, capture_output=True)
        cls.lib = C.CDLL(str(root/'images.so'))
        cls.lib.color_draw.restype = C.POINTER(C.c_ubyte*(320*200))
        cls.lib.color_total.restype = C.c_ulong

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, image, slot=0, **options):
        data = gif(image, **options)
        return self.lib.color_load(slot, data, len(data))

    def stored(self):
        w, h = self.lib.color_width(0), self.lib.color_height(0)
        return [[self.lib.color_stored(0, x, y) for x in range(w)] for y in range(h)]

    def check_draw(self, stored, width, height, x, y, top, bottom, right=312):
        frame = self.lib.color_draw(width, height, x, y, top, bottom, right).contents
        sh, sw = len(stored), len(stored[0])
        for py in range(200):
            for px in range(320):
                want = 0xee
                if (max(top, 0) <= py < min(bottom, 200) and y <= py < y+height and
                        x <= px < x+width and px < right):
                    source = stored[(py-y)*sh//height][(px-x)*sw//width]
                    if source >= 0: want = source
                if frame[py*320+px] != want:
                    self.fail('(%d,%d) is %d, expected %d for %r' %
                              (px, py, frame[py*320+px], want, (width, height, x, y, top, bottom, right)))
        self.assertEqual(C.c_uint.in_dll(self.lib, 'bad_rows').value, 0)

    def test_natural_size_draws_every_pixel_at_odd_and_even_positions(self):
        self.lib.ew_images_clear()
        self.assertEqual(self.load(indexed(61, 37, lambda x, y: (x*5 + y*3) % 16)), 0)
        stored = self.stored()
        self.assertEqual(stored[7][11], (11*5 + 7*3) % 16)
        for x, y, top, bottom in ((0, 40, 32, 188), (1, 40, 32, 188), (17, 30, 32, 188), (-5, 170, 32, 188),
                                  (-6, 20, 32, 60), (280, 50, 0, 200), (281, 180, 32, 188), (312, 50, 32, 188)):
            self.check_draw(stored, 61, 37, x, y, top, bottom)

    def test_transparent_pixels_leave_the_page_untouched(self):
        self.lib.ew_images_clear()
        self.assertEqual(self.load(indexed(40, 20, lambda x, y: 3 if (x + y) % 4 == 0 else 9), transparency=3), 0)
        stored = self.stored()
        self.assertEqual(sum(row.count(-1) for row in stored), 200)
        for x in (10, 11, -3, 290):
            self.check_draw(stored, 40, 20, x, 60, 32, 188)

    def test_enlarged_and_reduced_display_sizes_sample_by_floor(self):
        rng = random.Random(4)
        self.lib.ew_images_clear()
        self.assertEqual(self.load(indexed(50, 30, lambda x, y: (x + 2*y) % 16)), 0)
        stored = self.stored()
        for _ in range(60):
            width = rng.randrange(1, 304); height = rng.randrange(1, 200)
            self.check_draw(stored, width, height, rng.randrange(-40, 320), rng.randrange(-60, 200),
                            rng.randrange(0, 100), rng.randrange(100, 201), rng.choice((312, 320, 150)))

    def test_cache_is_bounded_and_degrades_instead_of_dropping_images(self):
        big = indexed(640, 480, lambda x, y: (x//16 + y//16) % 16)
        self.lib.ew_images_clear()
        sizes = []
        for slot in range(8):
            result = self.load(big, slot)
            if result: break
            sizes.append((self.lib.color_width(slot), self.lib.color_height(slot)))
            self.assertLessEqual(self.lib.color_total(), 81920)
        self.assertEqual(sizes[0], (266, 200))            # full size while there is room
        self.assertGreaterEqual(len(sizes), 4)            # later ones shrink, they do not vanish
        self.assertLess(sizes[-1][0], sizes[0][0])
        for width, height in sizes:                       # proportions survive every step
            self.assertLessEqual(abs(width*480 - height*640), 640*3)
        self.lib.ew_images_clear()
        self.assertEqual(self.lib.color_total(), 0)
        self.assertEqual(self.load(big), 0)
        self.assertEqual((self.lib.color_width(0), self.lib.color_height(0)), (266, 200))


class ColorLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-color-layout-')
        root = pathlib.Path(cls.tmp.name)
        (root/'extra.c').write_text(
            '#include "elksweb.h"\n'
            'unsigned run_color(unsigned i){return ew_doc.runs[i].color;}\n'
            'unsigned run_n(unsigned i){return ew_doc.runs[i].n;}\n'
            'unsigned page_color(int which){return which==0?ew_doc.page_bg:which==1?ew_doc.page_fg:ew_doc.page_link;}\n')
        src = ROOT/'src'
        sources = [src/(name + '.c') for name in ('html', 'url', 'net', 'memory')]
        sources += [ROOT/'font/font.c', ROOT/'font/body_font.c', ROOT/'tests/qa_core_shim.c', root/'extra.c']
        subprocess.run(['cc', '-shared', '-fPIC', '-g', '-DEW_HOST_TEST', '-I'+str(src), '-I'+str(ROOT/'font'),
                        '-I'+str(ROOT/'platform'), *map(str, sources), '-o', str(root/'core.so')],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(root/'core.so'))
        cls.lib.ew_parse.argtypes = [C.c_char_p, C.c_char_p]
        cls.lib.qa_run_data.restype = C.c_void_p

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def parse(self, html, color):
        C.c_int.in_dll(self.lib, 'ew_color').value = color
        C.c_int.in_dll(self.lib, 'ew_screen_width').value = 320 if color else 640
        C.c_int.in_dll(self.lib, 'ew_pixel_aspect').value = 1 if color else 2
        self.lib.ew_parse(html.encode(), b'file:/t.htm')
        runs = []
        for i in range(self.lib.qa_runs()):
            n = self.lib.run_n(i)
            text = C.string_at(self.lib.qa_run_data(i), n).decode('latin-1') if self.lib.qa_run_kind(i) == 0 else None
            runs.append((text, self.lib.run_color(i), self.lib.qa_x(i), self.lib.qa_run_kind(i), n,
                         self.lib.qa_run_width_field(i)))
        return runs

    def tearDown(self):
        self.parse('', 0)

    def test_font_colors_map_to_the_nearest_solid_colour(self):
        cases = {'red': 12, '#ff0000': 12, '#f00': 12, 'navy': 1, '#000080': 1, 'green': 2, 'lime': 10,
                 'maroon': 4, 'purple': 5, 'teal': 3, 'olive': 6, 'gray': 8, 'silver': 7, 'white': 15,
                 'black': 0, 'yellow': 14, 'aqua': 11, 'fuchsia': 13, 'blue': 9, '0000aa': 1, '#AA5500': 6,
                 'BLUE': 9}
        for value, expected in cases.items():
            runs = self.parse('<p>a <font color="%s">tinted</font> b</p>' % value, 1)
            colors = {text.strip(): color for text, color, *_ in runs if text}
            self.assertEqual(colors['tinted'], 16 + expected, value)
            self.assertEqual(colors['a'], 0); self.assertEqual(colors['b'], 0)
        for bad in ('', '#12', 'notacolor', '#12345g', '#1234567'):
            runs = self.parse('<p><font color="%s">plain</font></p>' % bad, 1)
            self.assertEqual([color for text, color, *_ in runs if text], [0], bad)

    def test_nested_fonts_restore_the_outer_colour(self):
        runs = self.parse('<font color=red>r <font color=blue>b</font> r2</font> d', 1)
        self.assertEqual([(t.strip(), c) for t, c, *_ in runs if t],
                         [('r', 28), ('b', 25), ('r2', 28), ('d', 0)])

    def test_body_colours_are_recorded_only_on_the_colour_display(self):
        html = '<body bgcolor="#000080" text="#ffffff" link=yellow><p>x</p></body>'
        self.parse(html, 1)
        self.assertEqual([self.lib.page_color(i) for i in range(3)], [17, 31, 30])
        self.parse(html, 0)
        self.assertEqual([self.lib.page_color(i) for i in range(3)], [0, 0, 0])

    def test_monochrome_layout_ignores_colour_markup(self):
        colored = '<body bgcolor=navy><p>one <font color=red>two</font> three <font color="#00f">four</font></p>'
        plain = '<body><p>one <font>two</font> three <font>four</font></p>'
        self.assertEqual(self.parse(colored, 0), self.parse(plain, 0))
        self.assertTrue(all(run[1] == 0 for run in self.parse(colored, 0)))

    def test_narrow_page_wraps_inside_312_columns_and_keeps_image_shape(self):
        words = ' '.join('word%d' % i for i in range(120))
        runs = self.parse('<p>' + words + '</p><hr><ul><li>' + words + '</ul>'
                          '<img src="a.gif" width="608" height="100"><img src="b.gif" width="100" height="50">', 1)
        self.assertGreater(len(runs), 10)
        body = self.lib.ew_body_width
        body.argtypes = [C.c_char_p, C.c_uint, C.c_int]
        for text, _, x, kind, n, w in runs:
            if text is not None:
                self.assertLessEqual(x + body(text.encode('latin-1'), len(text), 0), 312, text)
            elif kind == 5:                       # EW_RUN_IMAGE: n is width, w is rows
                self.assertLessEqual(x + n, 312)
        images = [(n, w) for text, _, x, kind, n, w in runs if kind == 5]
        self.assertEqual(images, [(304, 50), (100, 50)])


if __name__ == '__main__':
    unittest.main()
