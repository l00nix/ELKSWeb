"""Run the actual display driver against simulated BIOS/console/framebuffer I/O.

These tests verify the driver's decisions and memory operations, not physical
adapter or ia16 BIOS ABI compatibility; native QEMU/hardware tests remain needed.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = r'''
#define __far
extern unsigned char test_cga[65536], test_planar[65536];
#define FAR_BYTES(seg, off) (((seg)==0xb800 ? test_cga : test_planar)+(off))
#define DCGET_GRAPH 1
#define DCSET_KRAW 2
#define DCREL_KRAW 3
#define DCREL_GRAPH 4
int test_open(const char *, int, ...);
int test_close(int);
ssize_t test_read(int, void *, size_t);
ssize_t test_write(int, const void *, size_t);
int test_ioctl(int, unsigned long, ...);
int test_tcgetattr(int, struct termios *);
int test_tcsetattr(int, int, const struct termios *);
int test_isatty(int);
unsigned ew_test_bios_video(unsigned, unsigned *);
void ew_test_video_register(unsigned, unsigned);
#define open test_open
#define close test_close
#define read test_read
#define write test_write
#define ioctl test_ioctl
#define tcgetattr test_tcgetattr
#define tcsetattr test_tcsetattr
#define isatty test_isatty
'''
SOURCE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "DRIVER"
unsigned char test_cga[65536], test_planar[65536];
static unsigned char expected[65536];
static int oracle_right=640, oracle_top, oracle_bottom=480;
static int adapter=3, current_mode=3, mode_failure, terminal=1;
static int opens, closes, sets, graphics_lock, keyboard_lock, mice;
static unsigned port_count, port_values[8], port_numbers[8];
static struct termios console_term, initial_term;
static const char *input="";
int test_open(const char *path,int flags,...) {
 (void)flags;assert(!strcmp(path,"/dev/tty"));++opens;return 3;
}
int test_close(int fd) {assert(fd==3);++closes;return 0;}
ssize_t test_read(int fd,void *p,size_t n) {
 if(fd!=0 || !*input || !n)return -1;
 *(char*)p=*input++;return 1;
}
ssize_t test_write(int fd,const void *p,size_t n) {(void)p;assert(fd==3);return n;}
int test_ioctl(int fd,unsigned long request,...) {
 assert(fd==3);
 if(request==DCGET_GRAPH)++graphics_lock;
 else if(request==DCREL_GRAPH)--graphics_lock;
 else if(request==DCSET_KRAW)++keyboard_lock;
 else if(request==DCREL_KRAW)--keyboard_lock;
 else assert(0);
 return 0;
}
int test_tcgetattr(int fd,struct termios *term) {assert(fd==3);*term=console_term;return 0;}
int test_tcsetattr(int fd,int action,const struct termios *term) {
 (void)action;assert(fd==3);console_term=*term;return 0;
}
int test_isatty(int fd) {assert(fd==0);return terminal;}
unsigned ew_test_bios_video(unsigned ax,unsigned *bx) {
 if(ax==0x1a00) {
   if(adapter==3) { *bx=8;return 0x1a; }
   if(adapter==5) { *bx=11;return 0x1a; }
   return ax;
 }
 if(ax==0x1200) {
   if(adapter==1)*bx=0; /* 64KB EGA */
   if(adapter==2)*bx=1; /* 128KB color EGA */
   return ax;
 }
 if(ax==0x0f00)return 0x5000|current_mode;
 assert(ax<256);++sets;
 if(!mode_failure || ax==3)current_mode=ax;
 return ax;
}
void ew_test_video_register(unsigned port,unsigned value) {
 assert(port_count<8);port_numbers[port_count]=port;port_values[port_count++]=value;
}
void ew_mouse_init(void) {++mice;}
void ew_mouse_shutdown(void) {if(mice)--mice;}
static void setup(void) {
 memset(test_cga,0xa5,sizeof(test_cga));memset(test_planar,0xa5,sizeof(test_planar));
 memset(&initial_term,0,sizeof(initial_term));
 initial_term.c_lflag=ECHO|ICANON|ISIG;initial_term.c_iflag=ICRNL|IXON;
 console_term=initial_term;
}
static void restored(void) {
 assert(current_mode==3);assert(opens==closes);assert(!graphics_lock && !keyboard_lock && !mice);
 assert(!memcmp(&initial_term,&console_term,sizeof(initial_term)));
}
static void untouched(void) {
 unsigned i;assert(!opens && !sets && !port_count);
 for(i=0;i<65536;i++)assert(test_cga[i]==0xa5 && test_planar[i]==0xa5);
}
static unsigned at(int x,int y,int height) {
 return height==200 ? ((y%2)*8192+(y/2)*80+x/8) : y*80+x/8;
}
static void oracle_pixel(int x,int y,int color,int height) {
 unsigned p,mask;if(x<0||x>=640||y<0||y>=height||x>=oracle_right||y<oracle_top||y>=oracle_bottom)return;
 p=at(x,y,height);mask=128>>(x%8);
 if(color)expected[p]|=mask;else expected[p]&=~mask;
}
static void drawing(const char *mode,int height) {
 unsigned i,n=height==200?16384:height*80;
 unsigned char *frame=height==200?test_cga:test_planar;
 unsigned char *unused=height==200?test_planar:test_cga;
 int x,y,w,h,c,j,k;unsigned rng=1868088;
 assert(!ew_platform_init(mode));assert(ew_screen_height==height);
 assert(ew_pixel_aspect==(height==200?2:1));
 assert(current_mode==(height==200?6:height==350?16:18));
 for(i=0;i<65536;i++) {assert(frame[i]==(i<n?255:0xa5));assert(unused[i]==0xa5);}
 if(height==200)assert(!port_count);
 else {
  static const unsigned vals[]={0x0f02,0x0001,0x0003,0x0004,0x0005,0xff08};
  assert(port_count==6);
  for(i=0;i<6;i++){assert(port_values[i]==vals[i]);assert(port_numbers[i]==(i?0x3ce:0x3c4));}
 }
 memcpy(expected,frame,65536);
 oracle_right=640;oracle_top=0;oracle_bottom=height;ew_clip(640,0,height);
 for(i=0;i<2400;i++) {
  if(i>=1200 && !(i%100)) {
   static const int right_edges[]={0,1,623,624,639,640};
   oracle_right=right_edges[(i/100)%6];
   oracle_top=(i/100)%2 ? 22 : 0;
   oracle_bottom=(i/100)%3 ? height-8 : oracle_top;
   ew_clip(oracle_right,oracle_top,oracle_bottom);
  }
  rng=rng*1664525U+1013904223U;x=(rng>>16)%800-80;
  rng=rng*1664525U+1013904223U;y=(rng>>16)%(height+60)-30;
  rng=rng*1664525U+1013904223U;w=(rng>>16)%720-20;
  rng=rng*1664525U+1013904223U;h=(rng>>16)%70-10;c=rng&1;
  switch(i%4) {
   case 0:ew_pixel(x,y,c);oracle_pixel(x,y,c,height);break;
   case 1:ew_hline(x,y,w,c);for(j=0;j<w;j++)oracle_pixel(x+j,y,c,height);break;
   case 2:ew_fillrect(x,y,w,h,c);for(k=0;k<h;k++)for(j=0;j<w;j++)oracle_pixel(x+j,y+k,c,height);break;
   default:ew_rect(x,y,w,h,c);if(w>0&&h>0){for(j=0;j<w;j++){oracle_pixel(x+j,y,c,height);oracle_pixel(x+j,y+h-1,c,height);}for(k=0;k<h;k++){oracle_pixel(x,y+k,c,height);oracle_pixel(x+w-1,y+k,c,height);}}break;
  }
  assert(!memcmp(expected,frame,65536));
 }
 oracle_right=640;oracle_top=0;oracle_bottom=height;ew_clip(640,0,height);
 for(i=0;i<2;i++)for(x=631;x<640;x++)for(y=height-13;y<height;y++) {
  ew_cursor_shape(i);ew_cursor_show(x,y);ew_cursor_hide();assert(!memcmp(expected,frame,65536));
 }
 ew_platform_shutdown();restored();
}
int main(int argc,char **argv) {
 const char *which;assert(argc==2);which=argv[1];setup();
 if(!strcmp(which,"cga"))drawing("cga",200);
 else if(!strcmp(which,"ega")){adapter=2;drawing("ega",350);}
 else if(!strcmp(which,"vga"))drawing("vga",480);
 else if(!strcmp(which,"reject")) {
  adapter=0;assert(ew_platform_init("vga")==-1);assert(strstr(ew_platform_error(),"unavailable"));untouched();
  adapter=1;assert(ew_platform_init("ega")==-1);untouched();
  adapter=5;assert(ew_platform_init("vga")==-1);untouched();
  adapter=4;current_mode=7;assert(ew_platform_init("cga")==-1);untouched();
  adapter=3;assert(ew_platform_init("bogus")==-1);untouched();
 }
 else if(!strcmp(which,"failure")) {
  mode_failure=1;assert(ew_platform_init("vga")==-1);assert(opens==1&&sets==2&&!port_count);restored();
 }
 else if(!strcmp(which,"cancel")) {input="q\n";assert(ew_platform_init(0)==1);untouched();}
 else if(!strcmp(which,"nonterminal")) {terminal=0;assert(ew_platform_init(0)==-1);untouched();}
 else if(!strcmp(which,"prompt")) {input="2\n";assert(!ew_platform_init(0));assert(ew_screen_height==350);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"reinit")) {assert(!ew_platform_init("vga"));ew_platform_shutdown();assert(!ew_platform_init("cga"));assert(ew_screen_height==200);ew_platform_shutdown();restored();}
 else assert(0);
 return 0;
}
'''

class VideoModes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-video-')
        folder = pathlib.Path(cls.temp.name)
        (folder/'platform_test.h').write_text(HEADER)
        (folder/'driver.c').write_text(SOURCE.replace('DRIVER', str(ROOT/'platform/elks_platform.c')))
        cls.binary = folder/'video-test'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-DEW_PLATFORM_TEST',
                        '-I'+str(folder), '-I'+str(ROOT/'platform'),
                        str(folder/'driver.c'),str(ROOT/'platform/elks_keys.c'),
                        '-o',str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, case):
        result = subprocess.run([str(self.binary), case], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_cga_interleaved_framebuffer(self): self.run_case('cga')
    def test_ega_planar_framebuffer(self): self.run_case('ega')
    def test_vga_planar_framebuffer(self): self.run_case('vga')
    def test_unsupported_adapters_and_mode_preserve_console(self): self.run_case('reject')
    def test_bios_mode_failure_restores_console(self): self.run_case('failure')
    def test_menu_cancel_without_graphics(self): self.run_case('cancel')
    def test_menu_requires_terminal(self): self.run_case('nonterminal')
    def test_menu_selects_ega(self): self.run_case('prompt')
    def test_shutdown_and_reinit_geometry(self): self.run_case('reinit')

if __name__ == '__main__': unittest.main()
