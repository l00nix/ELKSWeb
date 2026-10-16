"""Image ALT storage/render clipping and per-image server-side map coordinates."""
import ctypes as C
import pathlib
import subprocess
import tempfile
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SHIM=r'''
#define ew_pixel ignored_pixel
#define ew_fillrect ignored_fillrect
#define ew_vline ignored_vline
#include "CORE_SHIM"
#undef ew_pixel
#undef ew_fillrect
#undef ew_vline
#include "elks_platform.h"
#include <string.h>
static unsigned count;
static unsigned char frame[200][640];
static int clip_top,clip_bottom;
void ew_pixel(int x,int y,int color) {
  /* Match actual platform clipping: rejected calls are not framebuffer stores. */
  if(x<0 || x>=640 || y<0 || y>=200 || y<clip_top || y>=clip_bottom)return;
  ++count;frame[y][x]=color ? 2 : 1;
}
void ew_fillrect(int x,int y,int w,int h,int color) {
  int row,col;
  for(row=0;row<h;++row)for(col=0;col<w;++col)ew_pixel(x+col,y+row,color);
}
void ew_vline(int x,int y,int h,int color) { ew_fillrect(x,y,1,h,color); }
void ew_rect(int x,int y,int w,int h,int color) {(void)x;(void)y;(void)w;(void)h;(void)color;}
void ew_glyph(int x,int y,unsigned char c,int fg,int bg) {(void)x;(void)y;(void)c;(void)fg;(void)bg;}
const char *alt_value(unsigned i) {return ew_image_alt(&ew_doc.runs[i]);}
int alt_map(unsigned i) {return ew_image_is_map(&ew_doc.runs[i]);}
int alt_point(unsigned i,int x,int y,unsigned *mx,unsigned *my) {
  return ew_image_map_point(&ew_doc.runs[i],x,y,mx,my);
}
unsigned alt_flags(unsigned i) {return ew_doc.links[i].flags;}
unsigned alt_render(unsigned i,int x,int y,int top,int bottom) {
  count=0;memset(frame,0,sizeof(frame));
  clip_top=top<0?0:top;clip_bottom=bottom>200?200:bottom;
  ew_image_draw(&ew_doc.runs[i],x,y,top,bottom,0);return count;
}
unsigned alt_bad_pixels(void) {
  unsigned bad=0;int x,y;
  for(y=0;y<200;y++)for(x=0;x<640;x++)
    if((y<clip_top || y>=clip_bottom) && frame[y][x])++bad;
  return bad;
}
const unsigned char *alt_pixels(void) {return &frame[0][0];}
'''

class ImageAlt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='elksweb-image-alt-')
        path=pathlib.Path(cls.temp.name);shim=path/'shim.c'
        shim.write_text(SHIM.replace('CORE_SHIM',str(ROOT/'tests/qa_core_shim.c')))
        lib=path/'alt.dylib'
        sources=[ROOT/'src'/(name+'.c') for name in ('html','url','net','memory','images')]
        sources += [ROOT/'font/font.c',ROOT/'font/body_font.c',ROOT/'image/gif.c',ROOT/'image/dimensions.c',shim]
        subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-DEW_QA_REAL_IMAGES',
                        '-I'+str(ROOT/'src'),'-I'+str(ROOT/'platform'),*map(str,sources),'-o',str(lib)],
                       check=True,capture_output=True)
        cls.lib=C.CDLL(str(lib));cls.lib.ew_parse.argtypes=[C.c_char_p,C.c_char_p]
        cls.lib.alt_pixels.restype=C.c_void_p;cls.lib.alt_value.restype=C.c_char_p;cls.lib.alt_point.argtypes=[C.c_uint,C.c_int,C.c_int,C.c_void_p,C.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_images_clear();cls.lib.ew_source_free();cls.temp.cleanup()

    def setUp(self):
        self.lib.ew_images_clear()

    def parse(self,text):
        self.lib.ew_parse(text.encode() if isinstance(text,str) else text,b'http://host/page')
        return [i for i in range(self.lib.qa_runs()) if self.lib.qa_run_kind(i)==5]

    def test_alt_entities_and_unicode_transliterate_for_display(self):
        i=self.parse('<img src="missing.gif" alt="Caf&#233; &amp; A—B…">')[0]
        self.assertEqual(self.lib.alt_value(i),b'Cafe & A-B...')
        self.assertFalse(self.lib.alt_map(i))
        self.assertGreater(self.lib.qa_run_length(i),16)
        self.assertGreaterEqual(self.lib.qa_run_width_field(i),12)

    def test_legacy_alt_bytes_and_unicode_entities(self):
        i=self.parse(b'<meta charset="windows-1252"><img src="missing.gif" alt="Caf\xe9 &eacute; \x93Hello\x94">')[0]
        self.assertEqual(self.lib.alt_value(i),b'Cafe e "Hello"')

    def test_empty_alt_and_non_image_run_are_safe(self):
        indices=self.parse('Text<img src="missing.gif">After')
        self.assertEqual(self.lib.alt_value(indices[0]),b'')
        self.assertIsNone(self.lib.alt_value(0))
        self.assertFalse(self.lib.alt_map(0))

    def test_bounded_alt_preserves_following_text(self):
        i=self.parse('<img src="missing.gif" alt="'+'A'*300+'"><p>AFTER</p>')[0]
        self.assertEqual(self.lib.alt_value(i),b'A'*127)
        self.assertTrue(self.lib.qa_truncated())
        self.assertGreater(self.lib.qa_runs(),1)

    def test_ismap_is_per_image_not_per_anchor(self):
        a,b=self.parse('<a href="/map"><img src="one.gif" ismap=""><img src="two.gif"></a>')
        self.assertTrue(self.lib.alt_map(a));self.assertFalse(self.lib.alt_map(b))
        self.assertTrue(self.lib.alt_flags(0)&2)
        c=self.parse('<img src="one.gif" ismap>')[0]
        self.assertFalse(self.lib.alt_map(c))

    def test_scaled_map_coordinates_use_natural_image_dimensions(self):
        src='file://'+str((ROOT/'tests/fixtures/image.gif').resolve())
        html=f'<a href="/map"><img src="{src}" ismap width="32" height="64" alt="Map"></a>'
        self.parse(html);self.lib.ew_images_load();i=self.parse(html)[0]
        mx=C.c_uint();my=C.c_uint()
        self.assertEqual(self.lib.alt_point(i,16,16,C.byref(mx),C.byref(my)),0)
        self.assertEqual((mx.value,my.value),(8,8))
        self.assertEqual(self.lib.alt_point(i,31,31,C.byref(mx),C.byref(my)),0)
        self.assertEqual((mx.value,my.value),(15,15))
        for x,y in ((-1,0),(32,0),(0,-1),(0,32)):
            self.assertEqual(self.lib.alt_point(i,x,y,C.byref(mx),C.byref(my)),-1)

    def test_missing_map_uses_displayed_cga_coordinates(self):
        i=self.parse('<a href="/map"><img src="missing.gif" width=100 height=80 ismap></a>')[0]
        mx=C.c_uint();my=C.c_uint()
        self.assertEqual(self.lib.alt_point(i,30,20,C.byref(mx),C.byref(my)),0)
        self.assertEqual((mx.value,my.value),(30,40))

    def test_placeholder_alt_never_paints_outside_viewport(self):
        i=self.parse('<img src="missing.gif" width=150 height=120 alt="A readable label">')[0]
        for x,y,top,bottom in ((0,22,22,192),(-70,22,22,192),(620,22,22,192),
                               (0,18,22,192),(0,185,22,192),(0,-20,0,200)):
            self.assertGreater(self.lib.alt_render(i,x,y,top,bottom),0)
            self.assertEqual(self.lib.alt_bad_pixels(),0,(x,y,top,bottom))

    def test_partial_label_pixels_equal_crop_of_full_label(self):
        i=self.parse('<img src="missing.gif" width=150 height=120 alt="Clipped label">')[0]
        self.lib.alt_render(i,0,22,0,200)
        full=C.string_at(self.lib.alt_pixels(),640*200)
        for top,bottom in ((25,192),(0,28),(25,28),(26,27)):
            self.lib.alt_render(i,0,22,top,bottom)
            clipped=C.string_at(self.lib.alt_pixels(),640*200)
            expected=bytes(640*top)+full[640*top:640*bottom]+bytes(640*(200-bottom))
            self.assertEqual(clipped,expected,(top,bottom))
            self.assertEqual(self.lib.alt_bad_pixels(),0)

if __name__=='__main__':unittest.main()
