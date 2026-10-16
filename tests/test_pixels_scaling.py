"""Image scaling against independent division/coverage pixel oracles.

The test translation unit includes production images.c unchanged so synthetic
bitmaps can enter its private cache without involving GIF encoding or HTTP.
"""
import ctypes as C
import pathlib
import random
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIM = r'''
#include <stdlib.h>
#include <string.h>
#include "IMAGES_SOURCE"
struct ew_document ew_doc;
int ew_screen_height=200, ew_pixel_aspect=2;
uint32_t ew_source_length;
static unsigned char frame[640*200], reference[640*200];
static unsigned calls, outside;
void *ew_far_alloc(unsigned long n) { return malloc(n); }
void ew_far_free(void *p) { free(p); }
void ew_copy_to_far(void *d,const void *s,unsigned n) { memcpy(d,s,n); }
void ew_copy_from_far(char *d,const char *s,unsigned n) {
  if(n) { strncpy(d,s,n-1); d[n-1]=0; }
}
unsigned char ew_source_byte(uint32_t n) { (void)n; return 0; }
const char *ew_source_error(void) { return ""; }
int32_t ew_fetch_to_fd(const char*u,int f,uint32_t c,char*v,char*e,unsigned n) {
  (void)u;(void)f;(void)c;(void)v;(void)e;(void)n;return -1;
}
void ew_rect(int x,int y,int w,int h,int c) {(void)x;(void)y;(void)w;(void)h;(void)c;}
void ew_glyph(int x,int y,unsigned char c,int f,int b) {(void)x;(void)y;(void)c;(void)f;(void)b;}
int ew_body_char_width(unsigned char c,int bold) {(void)c;(void)bold;return 8;}
void ew_body_draw(int x,int y,unsigned char c,int f,int b,int bold,int italic)
{(void)x;(void)y;(void)c;(void)f;(void)b;(void)bold;(void)italic;}
void ew_pixel(int x,int y,int color) {
  ++calls;
  if(x<0 || x>=640 || y<0 || y>=200) { ++outside; return; }
  frame[y*640+x]=(unsigned char)color;
}
void pixels_prepare(unsigned width,unsigned height,int transparent) {
  unsigned x,y;
  struct ew_gif *g;
  ew_images_clear();
  g=&images[0]; image_count=1;
  g->width=width;g->height=height;g->stride=(width+7)/8;
  g->pixels=calloc(g->stride,height);
  if(transparent)g->opacity=calloc(g->stride,height);
  for(y=0;y<height;++y)for(x=0;x<width;++x) {
    unsigned at=y*g->stride+x/8, mask=128>>(x&7);
    if((x*7+y*3)%11<5)g->pixels[at]|=mask;
    if(transparent && (x+2*y)%5)g->opacity[at]|=mask;
  }
}
int pixels_compare(unsigned width,unsigned height,int x,int y,int top,int bottom,int inverse) {
  static const unsigned char ordered[16]={0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
  unsigned row,col,sx,sy,at,mask,i;
  struct ew_run r;
  struct ew_gif *g=&images[0];
  memset(&r,0,sizeof(r));r.kind=EW_RUN_IMAGE;r.n=width;r.w=height;
  memset(frame,2,sizeof(frame));memset(reference,2,sizeof(reference));calls=outside=0;
  ew_image_draw(&r,x,y,top,bottom,inverse);
  for(row=0;row<height;++row) {
    long dy=(long)y+row;
    if(dy<top || dy>=bottom || dy<0 || dy>=200)continue;
    sy=(unsigned)((unsigned long)row*g->height/height);
    for(col=0;col<width;++col) {
      long dx=(long)x+col;
      if(dx<0 || dx>=640)continue;
      sx=(unsigned)((unsigned long)col*g->width/width);
      if(g->width>width || g->height/(unsigned)ew_pixel_aspect>height) {
        unsigned ex=(unsigned)((unsigned long)(col+1)*g->width/width);
        unsigned ey=(unsigned)((unsigned long)(row+1)*g->height/height);
        unsigned xx,yy,white=0,opaque=0,area;
        double threshold=(ordered[(row%4)*4+col%4]+0.5)/16.0;
        if(ex==sx)++ex;
        if(ey==sy)++ey;
        area=(ex-sx)*(ey-sy);
        for(yy=sy;yy<ey;++yy)for(xx=sx;xx<ex;++xx) {
          at=yy*g->stride+xx/8;mask=128>>(xx&7);
          if(!g->opacity || (g->opacity[at]&mask)) {
            ++opaque;
            if(g->pixels[at]&mask)++white;
          }
        }
        if((double)opaque/area>threshold)
          reference[dy*640+dx]=((double)white/area>threshold)^inverse;
      } else {
        at=sy*g->stride+sx/8;mask=128>>(sx&7);
        if(!g->opacity || (g->opacity[at]&mask))
          reference[dy*640+dx]=!!(g->pixels[at]&mask)^inverse;
      }
    }
  }
  if(outside)return -1;
  for(i=0;i<sizeof(frame);++i)if(frame[i]!=reference[i])return (int)i+1;
  return 0;
}

unsigned pixels_calls(void) { return calls; }
void pixels_pattern(unsigned kind) {
  unsigned x,y,at,mask;
  struct ew_gif *g=&images[0];
  pixels_prepare(16,32,kind>=3);
  memset(g->pixels,0,g->stride*g->height);
  if(g->opacity)memset(g->opacity,0,g->stride*g->height);
  for(y=0;y<g->height;++y)for(x=0;x<g->width;++x) {
    at=y*g->stride+x/8;mask=128>>(x&7);
    if(kind==1 || (kind==2 && x%2==0) || (kind==3 && y%4==0))g->pixels[at]|=mask;
    if(kind==3 && y%4<2)g->opacity[at]|=mask;
  }
}
unsigned pixels_color_count(unsigned color) {
  unsigned i,count=0;
  for(i=0;i<sizeof(frame);++i)if(frame[i]==color)++count;
  return count;
}
int pixels_decode(const unsigned char *blob,unsigned length,unsigned aspect) {
  ew_images_clear();image_count=1;ew_pixel_aspect=aspect;
  return ew_gif_decode_aspect(blob,length,&images[0],aspect);
}
const unsigned char *pixels_frame(void) { return frame; }

'''

class PixelScaling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='elksweb-scaling-')
        source=pathlib.Path(cls.temp.name)/'pixels.c'
        source.write_text(SHIM.replace('IMAGES_SOURCE',str(ROOT/'src/images.c')))
        library=source.with_suffix('.dylib')
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-O1',
                        '-DEW_HOST_TEST','-I'+str(ROOT/'src'),'-I'+str(ROOT/'platform'),
                        str(source),str(ROOT/'image/gif.c'),str(ROOT/'image/dimensions.c'),
                        '-o',str(library)],check=True,capture_output=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.pixels_prepare.argtypes=[C.c_uint,C.c_uint,C.c_int]
        cls.lib.pixels_compare.argtypes=[C.c_uint,C.c_uint,C.c_int,C.c_int,C.c_int,C.c_int,C.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_images_clear();cls.temp.cleanup()

    def compare(self, *args):
        self.assertEqual(self.lib.pixels_compare(*args),0,args)

    def test_enlargement_reduction_transparency_and_inverse(self):
        for sw,sh in ((1,1),(9,7),(17,31),(640,480)):
            for transparent in (0,1):
                self.lib.pixels_prepare(sw,sh,transparent)
                for width,height in ((1,1),(7,3),(16,16),(123,89),(616,200)):
                    for inverse in (0,1):
                        self.compare(width,height,7,22,22,192,inverse)

    def test_clipped_origins_preserve_sampling_phase(self):
        self.lib.pixels_prepare(127,97,1)
        for x,y in ((-83,-27),(-1,21),(600,180),(639,199),(-615,-199),(-616,0),(640,0),(0,200)):
            for inverse in (0,1):
                self.compare(616,200,x,y,22,192,inverse)

    def test_wide_destination_uses_bounded_unsigned_arithmetic(self):
        self.lib.pixels_prepare(640,480,1)
        for x in (-32768,-32000,-16000,0,639):
            self.compare(65535,255,x,-17,0,200,0)

    def test_no_pixels_for_zero_dimensions_or_empty_viewport(self):
        self.lib.pixels_prepare(16,16,0)
        for args in ((0,16,0,0,0,200,0),(16,0,0,0,0,200,0),(16,16,0,0,100,99,0)):
            self.compare(*args)
            self.assertEqual(self.lib.pixels_calls(),0)

    def test_only_visible_opaque_pixels_reach_platform(self):
        self.lib.pixels_prepare(640,480,0)
        self.compare(616,200,-610,0,22,192,0)
        self.assertEqual(self.lib.pixels_calls(),6*170)

    def test_reduced_gray_and_transparent_coverage(self):
        for pattern,white,black,opaque in ((0,0,64,64),(1,64,0,64),(2,32,32,64),(3,16,16,32),(4,0,0,0)):
            self.lib.pixels_pattern(pattern)
            self.compare(8,8,0,0,0,200,0)
            self.assertEqual(self.lib.pixels_calls(),opaque)
            self.assertEqual(self.lib.pixels_color_count(1),white)
            self.assertEqual(self.lib.pixels_color_count(0),black)
            self.compare(8,8,0,0,0,200,1)
            self.assertEqual(self.lib.pixels_color_count(1),black)
            self.assertEqual(self.lib.pixels_color_count(0),white)

    def test_square_pixel_reduction_and_cga_natural_size(self):
        aspect=C.c_int.in_dll(self.lib,'ew_pixel_aspect')
        try:
            for ratio in (1,2):
                aspect.value=ratio
                self.lib.pixels_prepare(32,32,1)
                self.compare(32,32//ratio,0,0,0,200,0)
                self.compare(16,16//ratio,-3,-2,0,200,0)
        finally:aspect.value=2

    def test_deterministic_random_scaling(self):
        rng=random.Random(8088)
        for _ in range(400):
            self.lib.pixels_prepare(rng.randrange(1,641),rng.randrange(1,481),rng.randrange(2))
            top=rng.randrange(-10,80);bottom=rng.randrange(100,211)
            self.compare(rng.randrange(1,1800),rng.randrange(1,256),rng.randrange(-1750,650),
                         rng.randrange(-250,210),top,bottom,rng.randrange(2))

if __name__=='__main__':unittest.main()
