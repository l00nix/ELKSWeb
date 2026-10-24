"""Exercise actual mouse initialization with recorded opens/termios calls.

The OS device calls are mocked; packet parsing has a separate C regression.
These tests establish selection/cleanup, not physical serial mouse operation.
"""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PLATFORM = Path(__file__).resolve().parents[1]
VARS = ('ELKSWEB_MOUSE', 'ELKSWEB_MOUSE_PORT', 'MOUSE_TYPE', 'MOUSE_PORT', 'QEMU')

class MouseConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ew-mouse-config-')
        root = Path(cls.tmp.name)
        (root/'shim.c').write_text(r'''
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <string.h>
static char opened[128];
static int flags, sets, closes, fail_open, fail_set;
static struct termios original, applied;
static unsigned char packet_bytes[256];
static int packet_pos, packet_len;
static ssize_t mock_read(int fd, void *buf, size_t n) {
  (void)fd; (void)n;
  if(packet_pos==packet_len) return 0;
  *(unsigned char *)buf=packet_bytes[packet_pos++]; return 1;
}
int ew_screen_height=200, ew_pixel_aspect=2;
static int mock_open(const char *path, int f, ...) {
  strcpy(opened,path); flags=f; return fail_open ? -1 : 42;
}
static int mock_close(int fd) {(void)fd; ++closes; return 0;}
static int mock_get(int fd, struct termios *t) {(void)fd; *t=original; return 0;}
static int mock_set(int fd, int action, const struct termios *t) {
  (void)fd; (void)action; ++sets; applied=*t; return fail_set && sets==1 ? -1 : 0;
}
#define open mock_open
#define close mock_close
#define tcgetattr mock_get
#define tcsetattr mock_set
#define read mock_read
#include "elks_mouse.c"
void qa_queue(int dx,int dy,unsigned buttons) {
  packet_bytes[packet_len++]=0xc0 | ((dx>>6)&3) | ((dy>>4)&12) | ((buttons&1)?32:0);
  packet_bytes[packet_len++]=0x80 | (dx&63); packet_bytes[packet_len++]=0x80 | (dy&63);
}
int qa_poll(int *result) {
  struct ew_mouse_event event;
  if(!ew_mouse_read(&event)) return 0;
  result[0]=event.x; result[1]=event.y; result[2]=event.pressed; result[3]=event.released;
  return 1;
}
int qa_motion(int dx,int dy,unsigned buttons,int *result) {
  packet_pos=packet_len=0; qa_queue(dx,dy,buttons); return qa_poll(result);
}
const char *qa_port(void) {return opened;}
int qa_exclusive(void) {return !!(flags&O_EXCL) && !!(flags&O_NOCTTY) && !!(flags&O_NONBLOCK);}
int qa_baud(void) {return cfgetispeed(&applied)==B1200 && cfgetospeed(&applied)==B1200;}
int qa_raw(void) {return !(applied.c_lflag&(ICANON|ECHO|ISIG)) && (applied.c_cflag&CSIZE)==CS8;}
int qa_restored(void) {return closes==1 && !memcmp(&original,&applied,sizeof(original));}
void qa_reset(int op, int set) {
  ew_mouse_shutdown(); memset(&original,0,sizeof(original));
  original.c_lflag=ICANON|ECHO|ISIG; original.c_cflag=CS7;
  cfsetispeed(&original,B9600); cfsetospeed(&original,B9600);
  packet_pos=packet_len=0; opened[0]=0; sets=closes=0; fail_open=op; fail_set=set;
}
''')
        subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',
                        '-I'+str(PLATFORM),str(root/'shim.c'),
                        str(PLATFORM/'elks_mouse_packet.c'),'-o',str(root/'mouse.so')],check=True)
        cls.lib=C.CDLL(str(root/'mouse.so'));cls.lib.qa_port.restype=C.c_char_p
    @classmethod
    def tearDownClass(cls): cls.lib.ew_mouse_shutdown();cls.tmp.cleanup()
    def config(self, env, fail_open=0, fail_set=0):
        self.lib.qa_reset(fail_open,fail_set)
        clean={k:v for k,v in os.environ.items() if k not in VARS}
        clean.update(env)
        with patch.dict(os.environ,clean,clear=True): self.lib.ew_mouse_init()
        return self.lib.qa_port().decode()
    def test_elks_defaults_and_configured_ports(self):
        for env,path in (({},'/dev/ttyS0'),({'QEMU':'1'},'/dev/ttyS1'),
                         ({'MOUSE_TYPE':'ps2'},'/dev/psaux'),
                         ({'MOUSE_TYPE':'ps2','MOUSE_PORT':'/dev/ttyS1'},'/dev/psaux'),
                         ({'MOUSE_PORT':'/dev/ttyS2'},'/dev/ttyS2'),
                         ({'MOUSE_TYPE':'ms','MOUSE_PORT':'/dev/ttyS1'},'/dev/ttyS1')):
            with self.subTest(env=env):
                self.assertEqual(self.config(env),path)
                self.assertEqual(self.lib.ew_mouse_present(),1)
                self.assertEqual(self.lib.qa_exclusive(),1)
                self.assertEqual(self.lib.qa_raw(),1)
                if env.get('MOUSE_TYPE')!='ps2': self.assertEqual(self.lib.qa_baud(),1)
                self.lib.ew_mouse_shutdown();self.assertEqual(self.lib.qa_restored(),1)
    def test_browser_overrides_and_empty_fallback(self):
        self.assertEqual(self.config({'MOUSE_TYPE':'ms','MOUSE_PORT':'/dev/ttyS0',
            'ELKSWEB_MOUSE':'ps2','ELKSWEB_MOUSE_PORT':'/dev/custom'}),'/dev/custom')
        self.assertEqual(self.config({'ELKSWEB_MOUSE':'','ELKSWEB_MOUSE_PORT':'',
            'MOUSE_TYPE':'ms','MOUSE_PORT':'/dev/ttyS2'}),'/dev/ttyS2')
    def test_disabled_and_unsupported_do_not_open(self):
        for env in ({'MOUSE_TYPE':'none'},{'ELKSWEB_MOUSE':'none'},
                    {'MOUSE_PORT':'none'},{'ELKSWEB_MOUSE_PORT':'none'},
                    {'MOUSE_TYPE':'pc'},{'ELKSWEB_MOUSE':'invalid'}):
            with self.subTest(env=env):
                self.assertEqual(self.config(env),'')
                self.assertEqual(self.lib.ew_mouse_present(),0)
    def test_busy_port_keeps_keyboard_available(self):
        self.assertEqual(self.config({},fail_open=1),'/dev/ttyS0')
        self.assertEqual(self.lib.ew_mouse_present(),0)
    def test_failed_setup_restores_settings_and_closes(self):
        self.config({},fail_set=1)
        self.assertEqual(self.lib.ew_mouse_present(),0)
        self.assertEqual(self.lib.qa_restored(),1)

    def test_half_speed_retains_small_motion_and_immediate_buttons(self):
        self.config({'ELKSWEB_MOUSE':'ms'})
        result=(C.c_int*4)()
        move=lambda x,y,b=0:self.lib.qa_motion(x,y,b,result)
        for _ in range(3): self.assertEqual(move(1,-1),1)
        self.assertEqual(move(1,-1),1)
        self.assertEqual(list(result)[:2],[322,98])
        self.assertEqual(move(0,0,1),1)
        self.assertEqual(list(result),[322,98,1,0])
        self.assertEqual(move(0,0,0),1)
        self.assertEqual(list(result),[322,98,0,1])
        self.assertEqual(move(-8,12),1)
        self.assertEqual(list(result)[:2],[318,104])
        for _ in range(3): self.assertEqual(move(-1,1),1)
        self.assertEqual(move(-1,1),1)
        self.assertEqual(list(result)[:2],[316,106])


    def test_queued_motion_coalesces_without_losing_button_edges(self):
        self.config({'ELKSWEB_MOUSE':'ms'})
        result=(C.c_int*4)()
        for x,y,b in [(10,0,0),(10,0,0),(0,0,1),(8,4,1),(0,0,0),(4,0,0)]:
            self.lib.qa_queue(x,y,b)
        for expected in ([330,100,1,0],[334,102,0,1],[336,102,0,0]):
            self.assertEqual(self.lib.qa_poll(result),1)
            self.assertEqual(list(result),expected)
        self.assertEqual(self.lib.qa_poll(result),0)

    def test_queued_motion_budget_is_bounded_and_keeps_remaining_packets(self):
        self.config({'ELKSWEB_MOUSE':'ms'})
        result=(C.c_int*4)()
        for _ in range(33): self.lib.qa_queue(2,0,0)
        self.assertEqual(self.lib.qa_poll(result),1)
        self.assertEqual(result[0],352)
        self.assertEqual(self.lib.qa_poll(result),1)
        self.assertEqual(result[0],353)
        self.assertEqual(self.lib.qa_poll(result),0)

if __name__=='__main__': unittest.main()
