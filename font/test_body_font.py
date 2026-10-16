import ctypes,pathlib,subprocess,tempfile,unittest
from generate_body import generate,body_glyphs,legacy_body_glyphs,small_regular_glyphs
HERE=pathlib.Path(__file__).resolve().parent
class BodyFont(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();p=pathlib.Path(cls.tmp.name)
  (p/'mock.c').write_text('unsigned char pixels[640*200]; void ew_fillrect(int x,int y,int w,int h,int c){int i,j;for(j=0;j<h;j++)for(i=0;i<w;i++)if(x+i>=0&&x+i<640&&y+j>=0&&y+j<200)pixels[(y+j)*640+x+i]=c;} void ew_pixel(int x,int y,int c){ew_fillrect(x,y,1,1,c);} void ew_vline(int x,int y,int h,int c){ew_fillrect(x,y,1,h,c);}')
  subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(HERE/'body_font.c'),str(p/'mock.c'),'-o',str(p/'body.so')],check=True)
  cls.small=small_regular_glyphs()
  cls.lib=ctypes.CDLL(str(p/'body.so'));cls.pixels=(ctypes.c_ubyte*(640*200)).in_dll(cls.lib,'pixels')
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_reproducible(self):self.assertEqual((HERE/'body_font.c').read_text(),generate())
 def test_all_pixels_and_advances(self):
  for bold,name in enumerate(['helvR08.bdf','helvB08.bdf']):
   for code,(advance,rows) in enumerate(body_glyphs(name,bold),32):
    for italic in [0,1]:
     ctypes.memset(self.pixels,0,len(self.pixels));self.lib.ew_body_draw(10,10,code,1,0,bold,italic)
     expected={(11+x+((7-y)//4 if italic else 0),10+y)for y,row in enumerate(rows)for x in range(16)if row&(0x8000>>x)}
     actual={(x,y)for y in range(10,18)for x in range(8,32)if self.pixels[y*640+x]}
     self.assertEqual(expected,actual,(code,bold,italic));self.assertEqual(self.lib.ew_body_char_width(code,bold),advance)
 def test_small_scale_pixels_and_advances(self):
  for bold,name in enumerate(['helvR08.bdf','helvB08.bdf']):
   for code,(advance,rows) in enumerate(body_glyphs(name,bold),32):
    for italic in [0,1]:
     ctypes.memset(self.pixels,0,len(self.pixels));self.lib.ew_small_draw(10,10,code,1,0,bold,italic)
     small_advance=(advance*3+2)//4
     expected=set()
     if not bold:
      for y,row in enumerate(self.small[code-32][1]):
       for x in range(16):
        if row&(0x8000>>x):
         dx=min(x+((5-y)//4 if italic else 0),small_advance-2)
         expected.add((10+dx,10+y))
     else:
      for y,row in enumerate(rows):
       if chr(code) in 'ij' and y==1:continue
       dy=2+(y-2)*3//(4 if chr(code)=='i' else 5) if chr(code) in 'ij' and y>=2 else y*3//4
       if dy>5:continue
       for x in range(16):
        if row&(0x8000>>x):
         dx=(x*(small_advance-2)+(advance-2)//2)//(advance-2)
         dx=min(dx+((7-y)//4 if italic else 0),small_advance-2)
         expected.add((10+dx,10+dy))
     actual={(x,y)for y in range(10,16)for x in range(8,30)if self.pixels[y*640+x]}
     self.assertEqual(expected,actual,(code,bold,italic));self.assertEqual(self.lib.ew_small_char_width(code,bold),(advance*3+2)//4)
  self.assertEqual(self.lib.ew_small_height(0),6)
 def test_small_spacing_and_dots(self):
  for bold in [0,1]:
   for code in range(33,127):
    ctypes.memset(self.pixels,0,len(self.pixels));self.lib.ew_small_draw(10,10,code,1,0,bold,0)
    advance=self.lib.ew_small_char_width(code,bold)
    self.assertFalse(any(self.pixels[y*640+10+advance-1]for y in range(10,16)))
   ctypes.memset(self.pixels,0,len(self.pixels));self.lib.ew_small_draw(10,10,ord('i'),1,0,bold,0)
   self.assertTrue(any(self.pixels[10*640+x]for x in range(10,14)))
   self.assertFalse(any(self.pixels[11*640+x]for x in range(10,14)))
   self.assertTrue(any(self.pixels[12*640+x]for x in range(10,14)))
 def test_small_face_preserves_counters_and_descender(self):
  glyphs=self.small
  def pixels(c):
   advance,rows=glyphs[ord(c)-32]
   return [[bool(row&(0x8000>>x))for x in range(advance-1)]for row in rows]
  # e retains a white counter above its crossbar, unlike stroke-merging shrink.
  e=pixels('e');self.assertTrue(e[2][0]);self.assertFalse(e[2][1]);self.assertTrue(e[3][1])
  self.assertNotEqual(pixels('i'),pixels('j'))
  self.assertTrue(any(pixels('j')[-1]))
  self.assertEqual(190+sum(6*(2 if a>9 else 1)for a,r in glyphs),778)
 def test_narrow_letters_remain_distinct(self):
  glyphs=body_glyphs('helvR08.bdf',0)
  t=glyphs[ord('t')-32][1];f=glyphs[ord('f')-32][1]
  self.assertNotEqual(t,f)
  self.assertEqual(t[0],0x6000) # Two centered physical pixels in a four-pixel crossbar.
  self.assertEqual(t[2],0xf000)
 def test_monospace_cells_keep_spacing(self):
  for size,height in [(0,6),(1,8),(2,10)]:
   for bold in [0,1]:
    for italic in [0,1]:
     for code in range(32,127):
      ctypes.memset(self.pixels,0,len(self.pixels))
      self.lib.ew_mono_draw(10,10,code,1,0,bold,italic,size)
      advance=self.lib.ew_mono_char_width(code,bold,size)
      ink={(x,y)for y in range(8,22)for x in range(8,27)if self.pixels[y*640+x]}
      self.assertTrue(all(10<=x<10+advance-1 and 10<=y<10+height for x,y in ink),(code,bold,italic,size))
      self.assertEqual(bool(ink),code!=32,(code,bold,italic,size))
 def test_advances_unchanged_and_table_budget(self):
  total=570
  for bold,name in enumerate(['helvR08.bdf','helvB08.bdf']):
   before=legacy_body_glyphs(name,bold);after=body_glyphs(name,bold)
   self.assertEqual([a for a,r in before],[a for a,r in after])
   total+=sum(8*(2 if a>9 else 1)for a,r in after)
  self.assertEqual(total,2506)
  self.assertLess(total-1710,1024)
 def test_geometry(self):
  self.assertEqual([self.lib.ew_body_char_width(ord(c),0)for c in 'Plain'],[9,3,7,3,7])
  text=b'First link | Redirect | Missing page'
  self.assertEqual(self.lib.ew_body_width(text,len(text),0),196)
  self.assertEqual(self.lib.ew_body_height(1),8)
if __name__=='__main__':unittest.main()
