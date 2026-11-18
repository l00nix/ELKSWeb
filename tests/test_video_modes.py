"""Run the actual display driver against simulated BIOS/console/framebuffer I/O.

These tests verify the driver's decisions and memory operations, not physical
adapter or ia16 BIOS ABI compatibility; native QEMU/hardware tests remain needed.
"""
import pathlib
import os
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
int test_dup(int);
int test_fcntl(int,int,...);
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
#define dup test_dup
#define fcntl test_fcntl
#define read test_read
#define write test_write
#define ioctl test_ioctl
#define tcgetattr test_tcgetattr
#define tcsetattr test_tcsetattr
#define isatty test_isatty
'''
SOURCE = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "DRIVER"
#include "elks_tandy.c"
/* No kernel colour reservation: these cases cover the monochrome adapters. */
static unsigned reserved_segment;
unsigned ew_test_color_probe(void) {return reserved_segment;}
unsigned char test_cga[65536], test_planar[65536];
static unsigned char expected[65536];
static int oracle_right=640, oracle_top, oracle_bottom=480;
static int adapter=3, current_mode=3, mode_failure, terminal=1;
static int opens, closes, sets, graphics_lock, keyboard_lock, mice;
static int open_error, console_flags, stdin_flags=O_RDWR, graph_failure, graph_calls, flag_failure;
static int get_failure, term_failure;
static unsigned prompt_bytes;
static unsigned port_count, port_values[8], port_numbers[8];
static struct termios console_term, initial_term;
static const char *input="";
int test_open(const char *path,int flags,...) {
 assert(!strcmp(path,"/dev/tty1"));assert(flags==O_RDWR);console_flags=flags;
 if(open_error){errno=open_error;return -1;}++opens;return 3;
}
int test_dup(int fd) {(void)fd;assert(0);return -1;}
int test_fcntl(int fd,int cmd,...) {
 va_list ap;int value;
 assert(cmd!=F_GETFL);
 assert(fd==3 && cmd==F_SETFL);va_start(ap,cmd);value=va_arg(ap,int);va_end(ap);
 if(flag_failure && (value&O_NONBLOCK))return -1;
 console_flags=value;return 0;
}
int test_close(int fd) {assert(fd==3);++closes;return 0;}
ssize_t test_read(int fd,void *p,size_t n) {
 size_t i=0;char ch,*out=p;
 assert(fd==3);
 if(console_flags&O_NONBLOCK)return -1;
 assert(console_term.c_lflag&ICANON);
 if(!*input || !n)return 0;
 /* ELKS ntty.c processes canonical erase within each individual read. */
 while(i<n && (ch=*input++)) {
  if(ch==8 || ch==127){if(i)--i;continue;}
  out[i++]=ch;if(ch=='\n')break;
 }
 return i;
}
ssize_t test_write(int fd,const void *p,size_t n) {(void)p;assert(fd==3);assert(!graphics_lock);if(!sets)prompt_bytes+=n;return n;}
int test_ioctl(int fd,unsigned long request,...) {
 assert(fd==3);
 if(request==DCGET_GRAPH){if(++graph_calls==graph_failure)return -1;assert(!graphics_lock);++graphics_lock;}
 else if(request==DCREL_GRAPH)--graphics_lock;
 else if(request==DCSET_KRAW)++keyboard_lock;
 else if(request==DCREL_KRAW)--keyboard_lock;
 else assert(0);
 return 0;
}
int test_tcgetattr(int fd,struct termios *term) {assert(fd==3);if(get_failure)return -1;*term=console_term;return 0;}
int test_tcsetattr(int fd,int action,const struct termios *term) {
 (void)action;assert(fd==3);if(term_failure){--term_failure;return -1;}console_term=*term;return 0;
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
 assert(port_count<8 || current_mode==18);if(port_count<8){port_numbers[port_count]=port;port_values[port_count]=value;}++port_count;
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
 assert(stdin_flags==O_RDWR);
 assert(current_mode==3);assert(opens==closes);assert(!graphics_lock && !keyboard_lock && !mice);
 assert(!memcmp(&initial_term,&console_term,sizeof(initial_term)));
}
static void untouched(void) {
 unsigned i;assert(opens==closes && !sets && !port_count);
 assert(!graphics_lock && !keyboard_lock && !mice);assert(!memcmp(&initial_term,&console_term,sizeof(initial_term)));
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
 else if(!strcmp(which,"vga"))drawing("vga-mono",480);
 else if(!strcmp(which,"reject")) {
  adapter=0;assert(ew_platform_init("vga")==-1);assert(strstr(ew_platform_error(),"unavailable"));untouched();
  adapter=1;assert(ew_platform_init("ega")==-1);untouched();
  adapter=5;assert(ew_platform_init("vga")==-1);untouched();
  adapter=4;current_mode=7;assert(ew_platform_init("cga")==-1);untouched();
  adapter=3;assert(ew_platform_init("bogus")==-1);untouched();
 }
 else if(!strcmp(which,"no_reservation")) {
  adapter=0;assert(ew_platform_init("tandy")==-1);
  assert(strstr(ew_platform_error(),"reservation"));untouched();
 }
 else if(!strcmp(which,"color_local")) {
  adapter=0;reserved_segment=0x9800;terminal=0;input="2\b\n";
  assert(!ew_platform_init(0));assert(prompt_bytes && ew_color && ew_screen_width==320);
  assert(current_mode==9 && keyboard_lock && keys.tandy);ew_platform_shutdown();restored();
 }
 else if(!strcmp(which,"pcjr_cooked")) {
  adapter=0;reserved_segment=0x1800;assert(!ew_platform_init("pcjr"));
  assert(ew_color && !keyboard_lock);ew_platform_shutdown();restored();
 }
 else if(!strcmp(which,"color_cancel")) {
  adapter=0;reserved_segment=0x9800;input="q\n";
  assert(ew_platform_init(0)==1);assert(prompt_bytes);untouched();
 }
 else if(!strcmp(which,"pcjr_then_vga")) {
  adapter=0;reserved_segment=0x1800;assert(!ew_platform_init("pcjr"));
  assert(!keyboard_lock);ew_platform_shutdown();adapter=3;reserved_segment=0;
  assert(!ew_platform_init("vga"));assert(ew_color && ew_screen_width==640);
  assert(keyboard_lock);ew_platform_shutdown();restored();
 }
 else if(!strcmp(which,"failure")) {
  mode_failure=1;assert(ew_platform_init("vga")==-1);assert(opens==1&&sets==2&&!port_count);restored();
 }
 else if(!strcmp(which,"cancel")) {input="q\n";assert(ew_platform_init(0)==1);untouched();}
 else if(!strcmp(which,"nonterminal")) {terminal=0;input="1\n";assert(!ew_platform_init(0));assert(prompt_bytes);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"prompt")) {input="2\n";assert(!ew_platform_init(0));assert(ew_screen_height==350);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"backspace")) {input="2\b3\n";assert(!ew_platform_init(0));assert(ew_screen_height==480);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"delete")) {input="3\1772\n";assert(!ew_platform_init(0));assert(ew_screen_height==350);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"erase_default")) {input="3\b\n";assert(!ew_platform_init(0));assert(ew_screen_height==200);ew_platform_shutdown();restored();}
 else if(!strcmp(which,"extra")) {input="23\n";assert(ew_platform_init(0)==-1);untouched();}
 else if(!strcmp(which,"long")) {input="22222222222222222222222222\n";assert(ew_platform_init(0)==-1);assert(!*input);untouched();}
 else if(!strcmp(which,"missing")) {open_error=ENODEV;assert(ew_platform_init("cga")==-1);assert(strstr(ew_platform_error(),"/dev/tty1"));untouched();}
 else if(!strcmp(which,"busy")) {graph_failure=1;input="1\n";assert(ew_platform_init(0)==-1);assert(!prompt_bytes);untouched();}
 else if(!strcmp(which,"relock")) {graph_failure=2;input="1\n";assert(ew_platform_init(0)==-1);assert(prompt_bytes);assert(strstr(ew_platform_error(),"busy"));restored();untouched();}
 else if(!strcmp(which,"flags")) {flag_failure=1;assert(ew_platform_init("cga")==-1);restored();untouched();}
 else if(!strcmp(which,"getattr")) {get_failure=1;assert(ew_platform_init("cga")==-1);restored();untouched();}
 else if(!strcmp(which,"setattr")) {term_failure=1;assert(ew_platform_init("cga")==-1);restored();untouched();}
 else if(!strcmp(which,"selector_attr")) {term_failure=1;assert(ew_platform_init(0)==-1);assert(!prompt_bytes);restored();untouched();}
 else if(!strcmp(which,"noncanonical_cancel")) {initial_term.c_lflag &= ~ICANON;console_term=initial_term;input="q\n";assert(ew_platform_init(0)==1);restored();untouched();}
 else if(!strcmp(which,"eof")) {input="";assert(ew_platform_init(0)==1);restored();untouched();}
 else if(!strcmp(which,"denied")) {open_error=EACCES;assert(ew_platform_init("cga")==-1);untouched();}
 else if(!strcmp(which,"redirected")) {terminal=0;stdin_flags=O_RDONLY;assert(!ew_platform_init("cga"));assert(stdin_flags==O_RDONLY);ew_platform_shutdown();assert(stdin_flags==O_RDONLY);stdin_flags=O_RDWR;restored();}
 else if(!strcmp(which,"cooked")) {assert(!ew_platform_init("cga"));assert(!keyboard_lock);ew_platform_shutdown();restored();}
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
        env=dict(os.environ, ELKSWEB_COOKED_KEYS='1' if case=='cooked' else '0')
        result = subprocess.run([str(self.binary), case], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_color_requires_kernel_reservation(self): self.run_case('no_reservation')
    def test_color_selector_retains_local_keyboard_and_backspace(self): self.run_case('color_local')
    def test_pcjr_uses_translated_keys(self): self.run_case('pcjr_cooked')
    def test_color_menu_cancel_restores_console(self): self.run_case('color_cancel')
    def test_pcjr_state_does_not_leak_into_later_vga_launch(self): self.run_case('pcjr_then_vga')
    def test_cga_interleaved_framebuffer(self): self.run_case('cga')
    def test_ega_planar_framebuffer(self): self.run_case('ega')
    def test_vga_planar_framebuffer(self): self.run_case('vga')
    def test_unsupported_adapters_and_mode_preserve_console(self): self.run_case('reject')
    def test_bios_mode_failure_restores_console(self): self.run_case('failure')
    def test_menu_cancel_without_graphics(self): self.run_case('cancel')
    def test_menu_uses_graphics_keyboard_without_terminal_stdin(self): self.run_case('nonterminal')
    def test_menu_selects_ega(self): self.run_case('prompt')
    def test_menu_backspace_reselects(self): self.run_case('backspace')
    def test_menu_delete_reselects(self): self.run_case('delete')
    def test_menu_erased_choice_defaults_to_cga(self): self.run_case('erase_default')
    def test_menu_rejects_multiple_choices(self): self.run_case('extra')
    def test_menu_drains_overlong_selection(self): self.run_case('long')
    def test_missing_graphics_keyboard_reports_device(self): self.run_case('missing')
    def test_busy_console_rejected_before_selector_or_changes(self): self.run_case('busy')
    def test_console_lock_failure_after_selector_restores_settings(self): self.run_case('relock')
    def test_nonblocking_flag_failure_restores_console(self): self.run_case('flags')
    def test_getattr_failure_releases_console(self): self.run_case('getattr')
    def test_raw_termios_failure_restores_console(self): self.run_case('setattr')
    def test_selector_termios_failure_restores_console(self): self.run_case('selector_attr')
    def test_noncanonical_selector_cancel_restores_settings(self): self.run_case('noncanonical_cancel')
    def test_selector_eof_restores_console(self): self.run_case('eof')
    def test_access_denied_does_not_fallback(self): self.run_case('denied')
    def test_redirected_stdin_is_not_used_or_modified(self): self.run_case('redirected')
    def test_hp_cooked_keys_do_not_request_raw_scancodes(self): self.run_case('cooked')
    def test_shutdown_and_reinit_geometry(self): self.run_case('reinit')

if __name__ == '__main__': unittest.main()
