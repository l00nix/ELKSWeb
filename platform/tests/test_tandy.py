"""Tandy/PCjr 16-colour raster: actual driver bytes against a pixel oracle.

Covers packed nibbles, the four interleaved banks, clipping at odd and even
edges, scrolling in both directions, the opaque/transparent row blit and
saving/restoring pixels under the pointer. Every framebuffer byte is
compared, including the unused tail of each bank and guard bytes on both
sides, so a stray write anywhere fails. Host C only: no timing or far-pointer
claim is made.
"""
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

PLATFORM = Path(__file__).resolve().parents[1]
GUARD = 4096


class TandyRaster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-tandy-')
        root = Path(cls.tmp.name)
        source = (PLATFORM/'elks_platform.c').read_text()
        routines = source[source.index('static unsigned scan_offset'):
                          len(source)]
        statics = '\n'.join(line for line in source.splitlines()
                            if line.startswith(('static int clip_', 'static int cursor_x',
                                                'static unsigned char cursor_')))
        (root/'tandy.c').write_text(
            '#include "elks_platform.h"\n#include "elks_tandy.c"\n'
            'unsigned char video[65536];\n'
            'int ew_screen_height=200,ew_pixel_aspect=1,ew_screen_width=320,ew_color=1;\n'
            'static unsigned video_bytes=16384;\n' + statics + '\n' + routines +
            'void test_base(unsigned char *p){ew_tandy_video=p;}\n')
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(PLATFORM), str(root/'tandy.c'), '-o', str(root/'tandy.so')],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(root/'tandy.so'))
        cls.buffer = (C.c_ubyte*(32768+2*GUARD))()
        cls.lib.test_base(C.byref(cls.buffer, GUARD))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        rng = random.Random(1986)
        self.seed = bytes(rng.randrange(256) for _ in range(len(self.buffer)))
        C.memmove(self.buffer, self.seed, len(self.seed))
        self.expected = bytearray(self.seed)
        self.clip = (320, 0, 200)
        self.lib.ew_clip(320, 0, 200)

    # Independent model of the documented layout.
    @staticmethod
    def at(x, y):
        return GUARD + (y % 4)*8192 + (y//4)*160 + x//2

    def put(self, x, y, color):
        right, top, bottom = self.clip
        if not (0 <= x < min(right, 320) and max(top, 0) <= y < min(bottom, 200)):
            return
        i = self.at(x, y)
        old = self.expected[i]
        self.expected[i] = (old & 0xf0) | color if x & 1 else (old & 0x0f) | (color << 4)

    def get(self, x, y):
        byte = self.buffer[self.at(x, y)]
        return byte & 15 if x & 1 else byte >> 4

    def set_clip(self, right, top, bottom):
        self.clip = (right, top, bottom)
        self.lib.ew_clip(right, top, bottom)

    def check(self, note=''):
        actual = bytes(self.buffer)
        if actual != bytes(self.expected):
            i = next(n for n in range(len(actual)) if actual[n] != self.expected[n])
            self.fail('%s: byte %d is %02x, expected %02x' % (note, i-GUARD, actual[i], self.expected[i]))

    def test_color_chart_reads_back_and_leaves_bank_padding_alone(self):
        self.lib.ew_clear(0)
        for y in range(200):
            for x in range(320):
                self.clip = (320, 0, 200); self.put(x, y, 0)
        for color in range(16):
            self.lib.ew_fillrect(color*20, 10+color, 20, 150, color)
            for y in range(10+color, 160+color):
                for x in range(color*20, color*20+20):
                    self.put(x, y, color)
        self.check('chart')
        for color in range(16):
            self.assertEqual(self.get(color*20+7, 100), color)
        # 192 bytes follow the 50 rows of every bank and belong to nobody.
        for bank in range(4):
            start = GUARD + bank*8192 + 8000
            self.assertEqual(bytes(self.buffer[start:start+192]), self.seed[start:start+192])

    def test_bank_boundaries_place_consecutive_rows_in_consecutive_banks(self):
        C.memset(self.buffer, 0, len(self.buffer))
        for y in range(8):
            self.lib.ew_pixel(0, y, y+1)
        for y in range(8):
            self.assertEqual(self.buffer[GUARD + (y % 4)*8192 + (y//4)*160], (y+1) << 4)
        self.lib.ew_pixel(319, 199, 9)
        self.assertEqual(self.buffer[GUARD + 3*8192 + 49*160 + 159], 9)

    def test_random_primitives_with_odd_and_even_clip_edges(self):
        rng = random.Random(7)
        for _ in range(1500):
            right = rng.choice((320, 312, 311, 1, 0, 157))
            top = rng.randrange(-5, 120); bottom = top + rng.randrange(0, 120)
            self.set_clip(right, top, bottom)
            x = rng.randrange(-30, 340); y = rng.randrange(-20, 220)
            w = rng.randrange(-3, 90); h = rng.randrange(-3, 40); color = rng.randrange(16)
            kind = rng.randrange(4)
            if kind == 0:
                self.lib.ew_pixel(x, y, color); self.put(x, y, color)
            elif kind == 1:
                self.lib.ew_hline(x, y, w, color)
                for i in range(max(w, 0)): self.put(x+i, y, color)
            elif kind == 2:
                self.lib.ew_fillrect(x, y, w, h, color)
                for j in range(max(h, 0)):
                    for i in range(max(w, 0)): self.put(x+i, y+j, color)
            else:
                self.lib.ew_vline(x, y, h, color)
                for j in range(max(h, 0)): self.put(x, y+j, color)
        self.check('primitives')

    def test_scroll_moves_only_the_page_columns_in_every_direction(self):
        for top, bottom in ((0, 200), (32, 188), (33, 187), (1, 6), (40, 41)):
            for delta in (1, -1, 2, -2, 3, -3, 4, -4, 13, -13, 50, -51, bottom-top-1, top-bottom+1,
                          bottom-top, 0):
                C.memmove(self.buffer, self.seed, len(self.seed))
                expected = bytearray(self.seed)
                if 0 < abs(delta) < bottom-top:
                    for y in range(top, bottom):
                        if top <= y+delta < bottom:
                            src = self.at(0, y+delta); dst = self.at(0, y)
                            expected[dst:dst+156] = self.seed[src:src+156]
                self.lib.ew_clip(0, 0, 0)       # scrolling ignores the raster clip
                self.lib.ew_scroll(top, bottom, delta)
                self.assertEqual(bytes(self.buffer), bytes(expected), (top, bottom, delta))

    def test_repeated_scrolling_leaves_no_trail(self):
        # Paint numbered rows, scroll up one text line at a time repainting the
        # exposed strip, and require the same picture as painting it directly.
        def paint(first, top, bottom):
            for y in range(top, bottom):
                self.lib.ew_hline(0, y, 312, (first+y) % 16)
        C.memset(self.buffer, 0, len(self.buffer))
        paint(0, 32, 188)
        offset = 0
        for step in (14, 14, 3, -5, 14, -14, 1, -1, 27):
            offset += step
            self.lib.ew_clip(320, 0, 200)
            self.lib.ew_scroll(32, 188, step)
            if step > 0: paint(offset, 188-step, 188)
            else: paint(offset, 32, 32-step)
        after = bytes(self.buffer)
        C.memset(self.buffer, 0, len(self.buffer))
        paint(offset, 32, 188)
        self.assertEqual(after, bytes(self.buffer))

    def test_row_blit_opaque_and_masked_at_every_phase(self):
        rng = random.Random(3)
        row4 = self.lib.ew_row4
        for _ in range(600):
            self.set_clip(rng.choice((320, 312, 201)), rng.randrange(0, 60), rng.randrange(60, 201))
            x = rng.randrange(0, 320); y = rng.randrange(0, 200); width = rng.randrange(0, 330-x)
            pixels = [rng.randrange(16) for _ in range(width)]
            masked = rng.random() < 0.5
            cover = [rng.random() < 0.6 for _ in range(width)]
            line = bytearray(162); mask = bytearray(41)
            for i, color in enumerate(pixels):
                n = i + (x & 1)
                line[n >> 1] |= color if n & 1 else color << 4
                if cover[i]: mask[i >> 3] |= 0x80 >> (i & 7)
            row4(x, y, bytes(line), bytes(mask) if masked else None, width)
            for i, color in enumerate(pixels):
                if not masked or cover[i]: self.put(x+i, y, color)
        self.check('row4')
        row4(-1, 5, bytes(162), None, 8)        # negative starts are the caller's to clip
        self.check('negative x ignored')

    def test_pointer_overlap_restores_every_byte(self):
        rng = random.Random(11)
        show, hide, shape = self.lib.ew_cursor_show, self.lib.ew_cursor_hide, self.lib.ew_cursor_shape
        for hand in (0, 1):
            shape(hand)
            for x, y in [(0, 0), (1, 0), (311, 0), (312, 5), (313, 7), (318, 100), (319, 199),
                         (0, 188), (5, 189), (7, 195), (160, 99), (161, 98)] + \
                        [(rng.randrange(320), rng.randrange(200)) for _ in range(200)]:
                show(x, y)
                # Outline black, interior white, nothing outside the 8x12 cell.
                changed = [(px, py) for py in range(200) for px in range(320)
                           if self.get(px, py) != (self.seed[self.at(px, py)] & 15 if px & 1
                                                   else self.seed[self.at(px, py)] >> 4)]
                for px, py in changed:
                    self.assertTrue(x <= px < x+8 and y <= py < y+12, (x, y, px, py))
                    self.assertIn(self.get(px, py), (0, 15))
                hide()
                self.assertEqual(bytes(self.buffer), self.seed, (hand, x, y))
        # Moving without hiding, changing shape while visible, then hiding.
        show(10, 10); show(12, 11); show(300, 195); shape(0); shape(1); hide()
        self.assertEqual(bytes(self.buffer), self.seed)
        # Drawing under a hidden pointer and showing it again must not resurrect old pixels.
        show(50, 50); hide(); self.lib.ew_fillrect(48, 48, 16, 16, 5); show(50, 50); hide()
        for py in range(48, 64):
            for px in range(48, 64):
                self.assertEqual(self.get(px, py), 5)


if __name__ == '__main__':
    unittest.main()
