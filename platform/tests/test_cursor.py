"""Compile actual drawing/cursor routines against guarded video memory.

BIOS/console setup is omitted. Production addressing, pixel clipping and saved
background routines run unchanged for CGA, EGA and VGA screen heights.
"""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest

PLATFORM = Path(__file__).resolve().parents[1]


class Cursor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-cursor-test-')
        root = Path(cls.tmp.name)
        source = (PLATFORM / 'elks_platform.c').read_text()
        globals_ = '\n'.join(line for line in source.splitlines()
                            if line.startswith(('static int clip_', 'static int cursor_',
                                                'static unsigned char cursor_')))
        routines = source[source.index('static unsigned scan_offset'):]
        mock = '''
#include "elks_platform.h"
unsigned char video[65536]={1};
int ew_screen_height=200, ew_pixel_aspect=2;
static unsigned video_bytes=16384;
'''
        (root / 'cursor.c').write_text(mock + globals_ + '\n' + routines)
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(PLATFORM), str(root/'cursor.c'),
                        '-o', str(root/'cursor.so')], check=True)
        cls.lib = C.CDLL(str(root/'cursor.so'))
        cls.video = (C.c_ubyte * 65536).in_dll(cls.lib, 'video')
        cls.height = C.c_int.in_dll(cls.lib, 'ew_screen_height')
        cls.original = bytes((i * 73 + i // 17) & 255 for i in range(65536))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def geometry(self, height):
        self.lib.ew_cursor_hide()
        self.lib.ew_cursor_shape(0)
        self.height.value = height
        C.memmove(self.video, self.original, len(self.original))

    def test_both_shapes_visible_on_white_and_inverted_black_background(self):
        for height in (200,350,480):
            self.geometry(height)
            self.lib.ew_clip(640,0,height)
            for background in (0,255):
                original=bytes([background])*len(self.video)
                for shape in (0,1):
                    self.lib.ew_cursor_hide()
                    C.memmove(self.video,original,len(original))
                    self.lib.ew_cursor_shape(shape)
                    self.lib.ew_cursor_show(320,height//2)
                    changed=sum(a!=b for a,b in zip(bytes(self.video),original))
                    self.assertGreater(changed,0,(height,background,shape))
                    self.lib.ew_cursor_hide()
                    self.assertEqual(bytes(self.video),original)

    def test_every_alignment_and_screen_edge_restores_exactly(self):
        for height in (200, 350, 480):
            self.geometry(height)
            for shape in (0, 1):
                self.lib.ew_cursor_shape(shape)
                for x in list(range(8)) + list(range(624, 640)):
                    for y in (0, 1, height-25, height-24, height-23, height-2, height-1):
                        self.lib.ew_cursor_show(x, y)
                        self.lib.ew_cursor_hide()
                        self.assertEqual(bytes(self.video), self.original, (height, shape, x, y))

    def test_arrow_has_doubled_bitmap_dimensions(self):
        self.geometry(200)
        self.lib.ew_clip(640,0,200)
        C.memset(self.video,255,len(self.video))
        self.lib.ew_cursor_show(320,80)
        pixels=[]
        for y in range(200):
            for x in range(640):
                offset=(y&1)*8192+(y>>1)*80+(x>>3)
                if not self.video[offset] & (128>>(x&7)): pixels.append((x,y))
        self.assertEqual((min(x for x,y in pixels),max(x for x,y in pixels)),(320,335))
        self.assertEqual((min(y for x,y in pixels),max(y for x,y in pixels)),(80,103))

    def test_byte_renderer_matches_original_bitmap_at_every_alignment(self):
        outlines=((0x80,0xc0,0xe0,0xf0,0xf8,0xfc,0xfe,0xff,0xf8,0xd8,0x8c,0x0c),
                  (0xc0,0xe0,0xe0,0xe0,0xfc,0xfe,0xff,0xff,0xff,0x7e,0x3e,0x3c))
        interiors=((0,0,0x40,0x60,0x70,0x78,0x7c,0x60,0x60,0x40,0,0),
                   (0,0x40,0x40,0x40,0x40,0x54,0x54,0x7e,0x3e,0x3c,0x1c,0))
        for height in (200,350,480):
            for shape in (0,1):
                for x in list(range(8))+list(range(624,640)):
                    for y in (1,height-23,height-1):
                        self.geometry(height)
                        self.lib.ew_cursor_shape(shape)
                        expected=bytearray(self.original)
                        for row in range(min(24,height-y)):
                            for col in range(min(16,640-x)):
                                bit=128>>(col//2)
                                if not outlines[shape][row//2]&bit: continue
                                px,py=x+col,y+row
                                offset=((py&1)*8192+(py>>1)*80 if height==200 else py*80)+(px>>3)
                                mask=128>>(px&7)
                                if interiors[shape][row//2]&bit: expected[offset]|=mask
                                else: expected[offset]&=255^mask
                        self.lib.ew_cursor_show(x,y)
                        self.assertEqual(bytes(self.video),bytes(expected),(height,shape,x,y))

    def test_visible_shape_change_and_move_preserve_background(self):
        for height in (200, 350, 480):
            self.geometry(height)
            self.lib.ew_cursor_show(319, height//2)
            arrow = bytes(self.video)
            self.lib.ew_cursor_shape(1)
            hand = bytes(self.video)
            self.assertNotEqual(arrow, hand)
            self.lib.ew_cursor_shape(0)
            self.assertEqual(bytes(self.video), arrow)
            self.lib.ew_cursor_shape(1)
            self.lib.ew_cursor_show(637, height-5)
            self.lib.ew_cursor_hide()
            self.assertEqual(bytes(self.video), self.original)

    def test_hidden_shape_change_and_invalid_positions_do_not_draw(self):
        for height in (200, 350, 480):
            self.geometry(height)
            self.lib.ew_cursor_shape(1)
            self.assertEqual(bytes(self.video), self.original)
            for x, y in [(-1, 0), (0, -1), (640, 100), (100, height)]:
                self.lib.ew_cursor_show(x, y)
                self.assertEqual(bytes(self.video), self.original)

    def test_redundant_shape_change_and_hide_are_idempotent(self):
        for height in (200, 350, 480):
            self.geometry(height)
            self.lib.ew_cursor_show(100, height-20)
            self.lib.ew_cursor_shape(1)
            before = bytes(self.video)
            self.lib.ew_cursor_shape(7)
            self.assertEqual(bytes(self.video), before)
            self.lib.ew_cursor_hide()
            self.lib.ew_cursor_hide()
            self.assertEqual(bytes(self.video), self.original)


if __name__ == '__main__':
    unittest.main()
