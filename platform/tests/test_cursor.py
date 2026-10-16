"""Compile the actual cursor routines against an emulated CGA byte array.

BIOS/console setup is omitted; saved-background and clipping code is unchanged.
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
        routines = source[source.index('void ew_cursor_hide(void)'):]
        mock = r'''
#include "elks_platform.h"
unsigned char video[16384];
static unsigned scan_offset(int x,int y) { return (y&1)*8192+(y>>1)*80+(x>>3); }
void ew_pixel(int x,int y,int white) {
    unsigned offset,mask;
    if(x<0||x>=640||y<0||y>=200)return;
    offset=scan_offset(x,y);mask=128U>>(x&7);
    if(white)video[offset]|=mask;else video[offset]&=~mask;
}
'''
        (root / 'cursor.c').write_text(mock + globals_ + '\n' + routines)
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(PLATFORM), str(root/'cursor.c'),
                        '-o', str(root/'cursor.so')], check=True)
        cls.lib = C.CDLL(str(root/'cursor.so'))
        cls.video = (C.c_ubyte * 16384).in_dll(cls.lib, 'video')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.lib.ew_cursor_hide()
        self.lib.ew_cursor_shape(0)
        self.original = bytes((i * 73 + i // 17) & 255 for i in range(16384))
        C.memmove(self.video, self.original, len(self.original))

    def test_every_alignment_and_screen_edge_restores_exactly(self):
        for shape in (0, 1):
            self.lib.ew_cursor_shape(shape)
            for x in list(range(8)) + list(range(632, 640)):
                for y in (0, 1, 187, 188, 189, 198, 199):
                    self.lib.ew_cursor_show(x, y)
                    self.lib.ew_cursor_hide()
                    self.assertEqual(bytes(self.video), self.original, (shape, x, y))

    def test_visible_shape_change_and_move_preserve_background(self):
        self.lib.ew_cursor_show(319, 97)
        arrow = bytes(self.video)
        self.lib.ew_cursor_shape(1)
        hand = bytes(self.video)
        self.assertNotEqual(arrow, hand)
        self.lib.ew_cursor_shape(0)
        self.assertEqual(bytes(self.video), arrow)
        self.lib.ew_cursor_shape(1)
        self.lib.ew_cursor_show(637, 195)
        self.lib.ew_cursor_hide()
        self.assertEqual(bytes(self.video), self.original)

    def test_hidden_shape_change_and_invalid_positions_do_not_draw(self):
        self.lib.ew_cursor_shape(1)
        self.assertEqual(bytes(self.video), self.original)
        for x, y in [(-1, 0), (0, -1), (640, 100), (100, 200)]:
            self.lib.ew_cursor_show(x, y)
            self.assertEqual(bytes(self.video), self.original)

    def test_redundant_shape_change_and_hide_are_idempotent(self):
        self.lib.ew_cursor_show(100, 100)
        self.lib.ew_cursor_shape(1)
        before = bytes(self.video)
        self.lib.ew_cursor_shape(7)
        self.assertEqual(bytes(self.video), before)
        self.lib.ew_cursor_hide()
        self.lib.ew_cursor_hide()
        self.assertEqual(bytes(self.video), self.original)


if __name__ == '__main__':
    unittest.main()
