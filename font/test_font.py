"""Compare the C rasterizer against all independently supplied ASCII BDF glyphs."""
import ctypes
import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('font_generator',HERE/'generate.py')
generator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class FontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        root=pathlib.Path(cls.temp.name)
        mock=root/'mock.c'
        mock.write_text('''
unsigned char pixels[640*200];
void ew_pixel(int x,int y,int c) { if(x>=0&&x<640&&y>=0&&y<200) pixels[y*640+x]=(unsigned char)c; }
void ew_fillrect(int x,int y,int w,int h,int c) { int i,j; for(j=0;j<h;j++) for(i=0;i<w;i++) ew_pixel(x+i,y+j,c); }
''')
        library=root/'font.so'
        subprocess.run(['cc','-shared','-fPIC','-std=c99','-Wall','-Wextra','-Werror',str(HERE/'font.c'),str(mock),'-o',str(library)],check=True)
        cls.lib=ctypes.CDLL(str(library))
        cls.pixels=(ctypes.c_ubyte*(640*200)).in_dll(cls.lib,'pixels')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_generated_source_reproducible(self):
        self.assertEqual((HERE/'font.c').read_text(),generator.generate())

    def test_all_ascii_glyphs_match_bdf(self):
        for bold,name in enumerate(['helvR08.bdf','helvB08.bdf']):
            for code,(advance,bearing,rows) in enumerate(generator.read_font(HERE/name),32):
                ctypes.memset(self.pixels,0,len(self.pixels))
                self.lib.ew_font_draw(10,10,code,1,0,bold)
                expected={(10+(bearing+x)*2+subpixel,10+y) for y,row in enumerate(rows) for x in range(8) for subpixel in range(2) if row&(128>>x)}
                actual={(x,y) for y in range(10,20) for x in range(8,30) if self.pixels[y*640+x]}
                self.assertEqual(actual,expected,(bold,code))
                self.assertEqual(self.lib.ew_font_char_width(code,bold),advance*2)

    def test_italic_shear_preserves_ink_and_advance(self):
        for bold,name in enumerate(['helvR08.bdf','helvB08.bdf']):
            for code,(advance,bearing,rows) in enumerate(generator.read_font(HERE/name),32):
                ctypes.memset(self.pixels,0,len(self.pixels))
                self.lib.ew_font_draw_italic(10,10,code,1,0,bold)
                expected={(10+(bearing+x)*2+subpixel+(9-y)//4,10+y) for y,row in enumerate(rows) for x in range(8) for subpixel in range(2) if row&(128>>x)}
                actual={(x,y) for y in range(10,20) for x in range(8,34) if self.pixels[y*640+x]}
                self.assertEqual(actual,expected,(bold,code))
                self.assertEqual(self.lib.ew_font_char_width(code,bold),advance*2)

    def test_width_and_fallback(self):
        self.assertEqual(self.lib.ew_font_width(b'iiiWWW',6,0),sum(self.lib.ew_font_char_width(c,0) for c in b'iiiWWW'))
        self.assertEqual(self.lib.ew_font_char_width(160,0),self.lib.ew_font_char_width(32,0))
        self.assertEqual(self.lib.ew_font_char_width(255,0),self.lib.ew_font_char_width(ord('?'),0))
        self.assertEqual(self.lib.ew_font_height(0),10)


if __name__=='__main__':unittest.main()
