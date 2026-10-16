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
                            if line.startswith(('static int cursor_',
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

    def test_every_alignment_and_screen_edge_restores_exactly(self):
        for height in (200, 350, 480):
            self.geometry(height)
            for shape in (0, 1):
                self.lib.ew_cursor_shape(shape)
                for x in list(range(8)) + list(range(632, 640)):
                    for y in (0, 1, height-13, height-12, height-11, height-2, height-1):
                        self.lib.ew_cursor_show(x, y)
                        self.lib.ew_cursor_hide()
                        self.assertEqual(bytes(self.video), self.original, (height, shape, x, y))

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
