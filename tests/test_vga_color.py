"""Production VGA raster against four independently stored video planes."""
import pathlib
import subprocess
import tempfile
import unittest
from test_video_modes import HEADER, SOURCE, ROOT

BODY = r'''
static unsigned char planes[4][65536];
static unsigned active, write_mode, write_mask;
static void sync_plane(void) { memcpy(planes[active],test_planar,65536); }
void ew_test_video_register(unsigned port,unsigned value) {
 if(port==0x3ce && (value&255)==5)write_mode=value>>8;
 if(port==0x3c4 && (value&255)==2)write_mask=value>>8;
 if(port==0x3ce && (value&255)==4) {
  sync_plane();active=value>>8;assert(active<4);
  memcpy(test_planar,planes[active],65536);
 }
}
void ew_test_latch_copy(unsigned to,unsigned from,unsigned count) {
 unsigned p;assert(write_mode==1 && write_mask==15);sync_plane();
 for(p=0;p<4;p++)memmove(planes[p]+to,planes[p]+from,count);
 memcpy(test_planar,planes[active],65536);
}
static unsigned pixel(int x,int y) {
 unsigned p,c=0;sync_plane();
 for(p=0;p<4;p++) if(planes[p][y*80+x/8]&(128>>(x&7))) c|=1<<p;
 return c;
}
int main(void) {
 unsigned x,y,p,i;unsigned char row[321],mask[80],saved[4][65536];
 setup();assert(!ew_platform_init("vga"));assert(ew_color && ew_screen_width==640 && ew_screen_height==480);
 for(p=0;p<16;p++) {ew_clear(p);assert(pixel(0,0)==p && pixel(639,479)==p);}
 ew_clear(3);
 for(p=0;p<16;p++) {ew_hline(p*39+1,70,39,p);for(x=p*39+1;x<(p+1)*39+1;x++)assert(pixel(x,70)==p);}
 ew_clip(623,20,470);ew_hline(-7,25,655,12);
 for(x=0;x<640;x++)assert(pixel(x,25)==(x<623?12:3));
 for(x=0;x<321;x++) row[x]=(x*37)&255;
 for(x=0;x<80;x++)mask[x]=(x*51)&255;
 for(i=0;i<8;i++) {
  ew_row4(i,30+i,row,mask,640-i);
  for(x=i;x<623;x++) {
   unsigned n=x-i+(i&1),want=mask[(x-i)/8]&(128>>((x-i)&7)) ? (n&1?row[n/2]&15:row[n/2]>>4) : 3;
   assert(pixel(x,30+i)==want);
  }
 }
 ew_clip(640,0,480);
 for(y=100;y<150;y++)ew_hline(0,y,640,y&15);
 ew_scroll(100,150,7);assert(write_mode==0);
 for(y=100;y<143;y++)for(x=0;x<640;x++)assert(pixel(x,y)==(x<624?(y+7)&15:y&15));
 ew_scroll(100,143,-5);assert(write_mode==0);
 for(y=105;y<143;y++)assert(pixel(300,y)==((y+2)&15));
 sync_plane();memcpy(saved,planes,sizeof(saved));
 for(i=0;i<2;i++)for(x=632;x<640;x++) {
  ew_cursor_shape(i);ew_cursor_show(x,470);ew_cursor_hide();sync_plane();assert(!memcmp(saved,planes,sizeof(saved)));
 }
 ew_platform_shutdown();restored();
 assert(!ew_platform_init("vga-mono"));assert(!ew_color);ew_platform_shutdown();
 assert(!ew_platform_init("cga"));assert(!ew_color);ew_platform_shutdown();
 return 0;
}
'''

class VGAColor(unittest.TestCase):
    def test_planes_rows_scroll_cursor_and_mode_switch(self):
        source=SOURCE[:SOURCE.index('int main(')]
        start=source.index('void ew_test_video_register(')
        end=source.index('void ew_mouse_init',start)
        source=source[:start]+source[end:]
        with tempfile.TemporaryDirectory() as temp:
            folder=pathlib.Path(temp)
            (folder/'platform_test.h').write_text(HEADER)
            (folder/'driver.c').write_text((source+BODY).replace('DRIVER',str(ROOT/'platform/elks_platform.c')))
            subprocess.run(['cc','-std=c99','-DEW_PLATFORM_TEST','-I'+str(folder),'-I'+str(ROOT/'platform'),str(folder/'driver.c'),str(ROOT/'platform/elks_keys.c'),'-o',str(folder/'test')],check=True,capture_output=True)
            subprocess.run([str(folder/'test')],check=True,timeout=10)

if __name__=='__main__': unittest.main()
