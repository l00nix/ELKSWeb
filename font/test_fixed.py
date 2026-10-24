"""Actual rasterizer against the separately supplied BDF glyphs and metrics."""
import ctypes as C
from pathlib import Path
import subprocess,tempfile,unittest
from generate_fixed import read_bdf,generate,FACES
HERE=Path(__file__).resolve().parent
class FixedFonts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name)
  (p/'mock.c').write_text('''
int ew_screen_height=200,ew_pixel_aspect=2;
unsigned char pixels[640*200];
void ew_pixel(int x,int y,int c){if(x>=0&&x<640&&y>=0&&y<200)pixels[y*640+x]=c;}
void ew_fillrect(int x,int y,int w,int h,int c){int i,j;for(j=0;j<h;j++)for(i=0;i<w;i++)ew_pixel(x+i,y+j,c);}
''')
  subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(HERE/'font.c'),str(HERE/'body_font.c'),str(p/'mock.c'),'-o',str(p/'font.so')],check=True)
  cls.lib=C.CDLL(str(p/'font.so'));cls.pixels=(C.c_ubyte*(640*200)).in_dll(cls.lib,'pixels')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_generated_tables_reproduce_exactly(self):self.assertEqual((HERE/'fixed_data.h').read_text(),generate())
 def test_every_ascii_glyph_style_size_and_polarity_matches_bdf(self):
  for size,h in enumerate((10,13,14)):
   for bold in (0,1):
    _,height,glyphs=read_bdf(HERE/FACES[0 if size==0 else (1 if size==1 else 3)+bold]);self.assertEqual(height,h)
    for italic in (0,1):
     for code in range(32,127):
      for inverse in (0,1):
       C.memset(self.pixels,inverse,len(self.pixels))
       self.lib.ew_face_draw(10,10,code,1-inverse,-1,bold,italic,size)
       expected=set()
       for y,row in enumerate(glyphs[code]):
        if size==0 and bold:row|=row>>1
        for x in range(8):
         if row&(128>>x):expected.add((10+x+((h-1-y)//6 if italic else 0),10+y))
       actual={(x,y)for y in range(10,10+h)for x in range(10,22)if self.pixels[y*640+x]!=inverse}
       self.assertEqual(actual,expected,(size,bold,italic,code,inverse))
 def test_cell_metrics_and_width_saturation(self):
  for size,height in enumerate((10,13,14)):
   for bold in (0,1):
    width=7 if size==2 or(size==0 and bold) else 6
    self.assertEqual(self.lib.ew_mono_height(size),height)
    self.assertEqual({self.lib.ew_mono_char_width(c,bold,size)for c in range(256)},{width})
    self.assertEqual(self.lib.ew_mono_width(b'Wi.!',4,bold,size),4*width)
    self.assertEqual(self.lib.ew_mono_width(b'x'*6000,6000,bold,size),32767)
 def test_fallback_and_nbsp(self):
  for code,reference in ((255,63),(1,63),(160,32)):
   C.memset(self.pixels,0,len(self.pixels));self.lib.ew_body_draw(20,20,code,1,0,0,0);actual=bytes(self.pixels)
   C.memset(self.pixels,0,len(self.pixels));self.lib.ew_body_draw(20,20,reference,1,0,0,0);self.assertEqual(actual,bytes(self.pixels))
 def test_small_steps_and_clipping_never_escape_framebuffer(self):
  for x,y in ((-8,-12),(-2,-2),(639,199),(640,200)):
   self.lib.ew_face_draw(x,y,ord('W'),1,-1,1,1,2)
 def test_independent_bold_and_open_counters(self):
  _,_,regular=read_bdf(HERE/'6x13.bdf');_,_,bold=read_bdf(HERE/'6x13B.bdf')
  self.assertNotEqual(regular[ord('a')],bold[ord('a')])
  for c in 'aeo068':
   rows=regular[ord(c)]
   self.assertTrue(any('101' in format(row,'08b') or '1001' in format(row,'08b') or '10001' in format(row,'08b') for row in rows),c)
if __name__=='__main__':unittest.main()
