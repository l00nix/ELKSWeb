"""Packed monochrome rows against a pixel oracle, including clipping and masks."""
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

PLATFORM = Path(__file__).resolve().parents[1]

class MonoRow(unittest.TestCase):
    def test_every_alignment_and_clipped_edge(self):
        source = (PLATFORM/'elks_platform.c').read_text()
        routines = source[source.index('static unsigned scan_offset'):source.index('void ew_cursor_hide(void)')]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'row.c').write_text('#include "elks_platform.h"\n#include "elks_tandy.c"\n'
                'unsigned char video[65536];\n'
                'int ew_screen_height=200,ew_pixel_aspect=2,ew_screen_width=640,ew_color;\n'
                'static unsigned video_bytes=16384;\n'+
                '\n'.join(s for s in source.splitlines() if s.startswith('static int clip_'))+'\n'+routines)
            subprocess.run(['cc','-O2','-shared','-fPIC','-Wall','-Wextra','-Werror','-I'+str(PLATFORM),str(root/'row.c'),'-o',str(root/'row.so')],check=True)
            lib=C.CDLL(str(root/'row.so'));video=(C.c_ubyte*65536).in_dll(lib,'video')
            lib.ew_row1.argtypes=[C.c_int,C.c_int,C.c_void_p,C.c_void_p,C.c_uint,C.c_int,C.c_int]
            height=C.c_int.in_dll(lib,'ew_screen_height')
            rng=random.Random(501)
            seed=bytes(rng.randrange(256) for _ in range(65536))
            cases=[(x,s,w) for x in range(-8,16) for s in range(8) for w in (1,6,7,8,9,15,16,79,640)]
            cases += [(x,rng.randrange(8),w) for x in (615,623,630,639,640,-32768,32767) for w in (0,1,8,17,640)]
            for h in (200,350,480):
                height.value=h
                for right,top,bottom in ((640,0,h),(624,17,h-19)):
                    lib.ew_clip(right,top,bottom)
                    for n,(x,start,width) in enumerate(cases):
                        y=[-1,0,1,16,17,18,h-20,h-19,h-1,h][n%10]
                        # Exact-size arrays catch accidental extra-byte reads under ASan too.
                        count=max(1,(start+max(0,width)+7)//8)
                        data=bytes(rng.randrange(256) for _ in range(count))
                        mask=bytes(rng.randrange(256) for _ in range(count)) if n%3 else None
                        inverse=n%2
                        expected=bytearray(seed)
                        for i in range(width):
                            sx=start+i;dx=x+i
                            if not(0<=dx<right and top<=y<bottom):continue
                            if mask and not(mask[sx//8]&(128>>(sx%8))):continue
                            row=(y%2)*8192+(y//2)*80 if h==200 else y*80
                            at=row+dx//8;bit=128>>(dx%8)
                            white=bool(data[sx//8]&(128>>(sx%8))) ^ bool(inverse)
                            if white:expected[at]|=bit
                            else:expected[at]&=255^bit
                        C.memmove(video,seed,len(seed));lib.ew_row1(x,y,data,mask,start,width,inverse)
                        self.assertEqual(bytes(video),expected,(h,right,top,bottom,x,y,start,width,inverse))

if __name__=='__main__':unittest.main()
