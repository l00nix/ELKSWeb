"""Decoded-bitmap cache in images.c: a second decode of the same GIF bytes for
the same display settings is read back from disk, and anything that does not
match exactly (other settings, a damaged or torn file) is decoded afresh.

Compiles the production images.c and GIF decoder with host stubs, like
test_color_page.py, so the cache code under test is the shipped code.
"""
import ctypes as C
import os
import pathlib
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MONO = (ROOT/'share/elksweb.gif').read_bytes()
TRANSPARENT = (ROOT/'share/nanox/webnx.gif').read_bytes()
COLOUR = (ROOT/'share/elkswebc.gif').read_bytes()
PHOTO = (ROOT/'tests/fixtures/frogfind/frog.gif').read_bytes()

SHIM = r'''
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include "IMAGES_SOURCE"
struct ew_document ew_doc;
int ew_screen_height=200,ew_pixel_aspect=1,ew_screen_width=640,ew_color=0;
uint32_t ew_source_length;
void *ew_far_alloc(unsigned long n) { return malloc(n); }
void ew_far_free(void *p) { free(p); }
void ew_copy_to_far(void *d,const void *s,unsigned n) { memcpy(d,s,n); }
void ew_copy_from_far(char *d,const char *s,unsigned n) { if(n) { strncpy(d,s,n-1); d[n-1]=0; } }
unsigned char ew_source_byte(uint32_t n) { (void)n; return 0; }
const char *ew_source_error(void) { return ""; }
int32_t ew_fetch_to_fd(const char*u,int f,uint32_t c,char*v,char*e,unsigned n) {
  (void)u;(void)f;(void)c;(void)v;(void)e;(void)n;return -1; }
void ew_rect(int x,int y,int w,int h,int c) {(void)x;(void)y;(void)w;(void)h;(void)c;}
void ew_glyph(int x,int y,unsigned char c,int f,int b) {(void)x;(void)y;(void)c;(void)f;(void)b;}
int ew_body_char_width(unsigned char c,int bold) {(void)c;(void)bold;return 8;}
void ew_body_draw(int x,int y,unsigned char c,int f,int b,int bold,int italic)
{(void)x;(void)y;(void)c;(void)f;(void)b;(void)bold;(void)italic;}
void ew_pixel(int x,int y,int color) {(void)x;(void)y;(void)color;}
void ew_row1(int x,int y,const unsigned char *b,const unsigned char *m,unsigned s,int w,int i)
{(void)x;(void)y;(void)b;(void)m;(void)s;(void)w;(void)i;}
void ew_row4(int x,int y,const unsigned char *l,const unsigned char *m,int w)
{(void)x;(void)y;(void)l;(void)m;(void)w;}
void qa_mode(int color,int aspect) { ew_color=color; ew_pixel_aspect=aspect; color_bytes=0; }
int qa_decode(const unsigned char *data,unsigned size) {
  ew_gif_free(&images[0]); color_bytes=0;
  return decode(data,size,&images[0]);
}
/* width,height,stride,depth,opacity bytes (0 if opaque), then the planes. */
unsigned qa_dump(unsigned char *out,unsigned cap) {
  struct ew_gif *g=&images[0];
  unsigned p=g->stride*g->height, o=g->opacity ? (unsigned)cache_opacity_bytes(g->depth,g->width,g->height,g->stride) : 0;
  unsigned need=10+p+o;
  if (!g->pixels || need>cap) return 0;
  out[0]=g->width; out[1]=g->width>>8; out[2]=g->height; out[3]=g->height>>8;
  out[4]=g->stride; out[5]=g->stride>>8; out[6]=g->depth; out[7]=0; out[8]=o; out[9]=o>>8;
  memcpy(out+10,g->pixels,p); if (o) memcpy(out+10+p,g->opacity,o);
  return need;
}
unsigned qa_head_size(void) { return sizeof(struct cache_head); }
unsigned qa_check_offset(void) { return offsetof(struct cache_head,check1); }
'''


def fletcher(data, a=0, b=0):
    for byte in data:
        a = (a + byte) & 0xffff
        b = (b + a) & 0xffff
    return a, b


class GifCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-gifcache-')
        base = pathlib.Path(cls.temp.name)
        shim = base/'shim.c'
        shim.write_text(SHIM.replace('IMAGES_SOURCE', str(ROOT/'src/images.c')))
        library = base/'gifcache.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-g', '-Wall', '-DEW_HOST_TEST',
                        '-I'+str(ROOT/'src'), '-I'+str(ROOT/'font'), '-I'+str(ROOT/'platform'),
                        str(shim), str(ROOT/'image/gif.c'), str(ROOT/'image/dimensions.c'),
                        '-o', str(library)], check=True)
        cls.lib = C.CDLL(str(library))
        cls.lib.qa_decode.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.qa_dump.argtypes = [C.c_void_p, C.c_uint]
        cls.lib.qa_dump.restype = C.c_uint

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix='ewc', dir='/tmp')
        os.environ['EW_GIFCACHE'] = self.dir.name
        self.lib.qa_mode(0, 1)

    def tearDown(self):
        os.environ.pop('EW_GIFCACHE', None)
        self.dir.cleanup()

    def files(self):
        return sorted(pathlib.Path(self.dir.name).iterdir())

    def decoded(self, data):
        self.assertEqual(self.lib.qa_decode(data, len(data)), 0)
        buffer = C.create_string_buffer(200000)
        size = self.lib.qa_dump(buffer, len(buffer))
        self.assertGreater(size, 0)
        return buffer.raw[:size]

    def fresh(self, data):
        """The decoder's own output, with the cache switched off."""
        saved = os.environ['EW_GIFCACHE']
        os.environ['EW_GIFCACHE'] = '0'
        try:
            return self.decoded(data)
        finally:
            os.environ['EW_GIFCACHE'] = saved

    def rewrite_planes(self, path, change):
        raw = bytearray(path.read_bytes())
        head, check = self.lib.qa_head_size(), self.lib.qa_check_offset()
        planes = bytearray(raw[head:])
        change(planes)
        raw[head:] = planes
        raw[check:check+4] = struct.pack('=HH', *fletcher(planes))
        path.write_bytes(bytes(raw))

    def test_second_decode_is_read_back_from_disk(self):
        for mode, data in (((0, 1), MONO), ((0, 2), PHOTO), ((0, 1), TRANSPARENT),
                           ((1, 1), COLOUR), ((1, 1), TRANSPARENT)):
            with self.subTest(mode=mode, size=len(data)):
                for path in self.files():
                    path.unlink()
                self.lib.qa_mode(*mode)
                expected = self.fresh(data)
                self.assertEqual(self.files(), [])
                self.assertEqual(self.decoded(data), expected)
                [path] = self.files()
                # Prove the second load is a cache hit: a validly checksummed
                # edit to the stored planes must show up in the result.
                self.rewrite_planes(path, lambda p: p.__setitem__(0, p[0] ^ 0xff))
                hit = self.decoded(data)
                self.assertNotEqual(hit, expected)
                self.assertEqual(hit[:10], expected[:10])
                self.assertEqual(hit[10] ^ 0xff, expected[10])

    def test_other_display_settings_do_not_share_entries(self):
        self.lib.qa_mode(0, 1)
        square = self.decoded(PHOTO)
        self.lib.qa_mode(0, 2)
        cga = self.decoded(PHOTO)
        self.assertEqual(cga, self.fresh(PHOTO))
        self.assertNotEqual(square, cga, 'CGA aspect changes the dither phase')
        self.lib.qa_mode(1, 1)
        self.assertEqual(self.decoded(PHOTO), self.fresh(PHOTO))

    def test_changed_image_bytes_miss(self):
        self.decoded(MONO)
        other = self.decoded(TRANSPARENT)
        self.assertEqual(other, self.fresh(TRANSPARENT))

    def test_damaged_or_torn_entries_are_decoded_again(self):
        expected = self.fresh(MONO)
        self.decoded(MONO)
        [path] = self.files()
        good = path.read_bytes()
        damaged = bytearray(good)
        damaged[-1] ^= 1
        for broken in (bytes(damaged), good[:-1], good[:self.lib.qa_head_size()],
                       b'\0' * 4 + good[4:], b''):
            with self.subTest(size=len(broken)):
                path.write_bytes(broken)
                self.assertEqual(self.decoded(MONO), expected)
                self.assertEqual(path.read_bytes(), good, 'a bad entry is rewritten')

    def test_disabled_or_unusable_directory_writes_nothing(self):
        os.environ['EW_GIFCACHE'] = '0'
        self.decoded(MONO)
        self.assertEqual(self.files(), [])
        os.environ['EW_GIFCACHE'] = self.dir.name + '/missing'
        self.assertEqual(self.decoded(MONO), self.fresh(MONO))
        os.environ['EW_GIFCACHE'] = '/' + 'x' * 60
        self.assertEqual(self.decoded(MONO), self.fresh(MONO))


if __name__ == '__main__':
    unittest.main()
