"""Actual driver scroll bytes versus immutable independent framebuffer oracle.

Checks every byte, including CGA bank holes, scrollbar columns, exposed strips,
chrome and memory beyond the adapter framebuffer. No timing claim is made.
"""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest

PLATFORM=Path(__file__).resolve().parents[1]


class ScrollRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='ew-scroll-driver-')
        root=Path(cls.tmp.name)
        source=(PLATFORM/'elks_platform.c').read_text()
        routines=source[source.index('static unsigned scan_offset'):
                        source.index('void ew_cursor_hide(void)')]
        (root/'scroll.c').write_text(
            '#include "elks_platform.h"\nunsigned char video[65536];\n'
            'int ew_screen_height=200, ew_pixel_aspect=2;\n'
            'static unsigned video_bytes=16384;\n'+
            '\n'.join(line for line in source.splitlines()
                      if line.startswith('static int clip_'))+'\n'+routines)
        subprocess.run(['cc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',
                        '-I'+str(PLATFORM),str(root/'scroll.c'),'-o',str(root/'scroll.so')],
                       check=True,capture_output=True)
        cls.lib=C.CDLL(str(root/'scroll.so'))
        cls.video=(C.c_ubyte*65536).in_dll(cls.lib,'video')
        cls.height=C.c_int.in_dll(cls.lib,'ew_screen_height')
        cls.seed=bytes((i*73+i//17+i//8192*39)&255 for i in range(65536))
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    @staticmethod
    def offset(y,height): return (y%2)*8192+(y//2)*80 if height==200 else y*80

    def compare(self,height,top,bottom,delta):
        self.height.value=height
        C.memmove(self.video,self.seed,len(self.seed))
        expected=bytearray(self.seed)
        if 0<=top<bottom<=height and 0<abs(delta)<bottom-top:
            for y in range(top,bottom):
                source=y+delta
                if top<=source<bottom:
                    src=self.offset(source,height);dest=self.offset(y,height)
                    expected[dest:dest+78]=self.seed[src:src+78]
        # Explicit contract: scroll moves the whole viewport regardless of
        # raster clip; caller restores clipping for the exposed-strip redraw.
        self.lib.ew_clip(0,0,0)
        self.lib.ew_scroll(top,bottom,delta)
        self.assertEqual(bytes(self.video),expected,(height,top,bottom,delta))

    def test_bank_overlap_and_both_directions_preserve_every_other_byte(self):
        for height in (200,350,480):
            for top,bottom in ((0,height),(22,height-8),(23,height-9),(1,7),(31,32)):
                span=bottom-top
                for delta in (0,1,-1,2,-2,3,-3,7,-7,10,-10,span-1,1-span,span,-span):
                    with self.subTest(height=height,top=top,bottom=bottom,delta=delta):
                        self.compare(height,top,bottom,delta)

    def test_invalid_ranges_are_noops(self):
        for height in (200,350,480):
            for top,bottom in ((-1,height),(0,height+1),(height,0),(1,1),
                               (-32768,32767),(32767,32767),(0,-1)):
                for delta in (-32768,-1,0,1,32767):
                    self.compare(height,top,bottom,delta)


if __name__=='__main__': unittest.main()
