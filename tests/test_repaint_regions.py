"""Write-level regression for actual main.c renderer (not image equality).

Real fonts/parser/images write to an instrumented host framebuffer; every store
is counted even when the color is unchanged. The separate actual-driver suite
checks clipping/CGA-bank/planar safety. This does not measure physical HP timing.
"""
import ctypes as C
import pathlib
import os
from test_core_regression import OneHTTP
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAGE=(b'<title>Stable chrome</title><a href="/next">First link</a>'
      b'<form><input name=q value=seed><input type=submit value=Go></form>'
      +b'<p>Repeated line for scrolling.</p>'*45)

class RepaintRegions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='ew-repaint-')
        so=pathlib.Path(cls.tmp.name)/'repaint.so'
        sources=[ROOT/'src'/(s+'.c') for s in ('html','url','net','images','memory')]
        sources += [ROOT/'font/font.c',ROOT/'font/body_font.c',ROOT/'image/gif.c',
                    ROOT/'image/dimensions.c',ROOT/'tests/qa_repaint_shim.c']
        result=subprocess.run(['cc','-shared','-fPIC','-g','-Wall','-Wextra',
            '-DEW_HOST_TEST','-I'+str(ROOT/'src'),'-I'+str(ROOT/'platform'),
            *map(str,sources),'-o',str(so)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        cls.lib=C.CDLL(str(so))
        cls.lib.qa_repaint_prepare.argtypes=[C.c_char_p,C.c_int]
        cls.lib.qa_repaint_status.argtypes=[C.c_char_p]
        cls.lib.qa_repaint_progress.argtypes=[C.c_char_p]
        for name in ("load","bad_address","save"):
            getattr(cls.lib,"qa_repaint_"+name).argtypes=[C.c_char_p]
        cls.lib.qa_repaint_writes.restype=C.c_ulong
    @classmethod
    def tearDownClass(cls):cls.lib.qa_repaint_cleanup();cls.tmp.cleanup()
    def setUp(self):self.old_proxy=os.environ.pop("HTTP_PROXY",None)
    def tearDown(self):
        if self.old_proxy is not None:os.environ["HTTP_PROXY"]=self.old_proxy
    def prepare(self,height=200,html=PAGE):
        self.height=height;self.lib.qa_repaint_prepare(html,height)
    def count(self,x0,y0,x1,y1):return self.lib.qa_repaint_writes(x0,y0,x1,y1)
    def no_full_clear(self):self.assertEqual(self.lib.qa_repaint_clears(),0)
    def reset(self):self.lib.qa_repaint_writes_reset()
    def assert_header_untouched(self):
        self.no_full_clear();self.assertEqual(self.count(0,0,640,22),0)
        self.assertEqual(self.count(624,22,625,self.height-8),0)
        self.assertEqual(self.count(639,22,640,self.height-8),0)
    def test_scroll_never_writes_unchanged_chrome(self):
        for h in (200,350,480):
            with self.subTest(height=h):
                self.prepare(h);self.lib.qa_repaint_key(1)
                self.assert_header_untouched()
                self.assertGreater(self.count(0,22,624,h-8),0)
    def test_focus_page_highlight_keeps_title_address_frame(self):
        self.prepare();self.lib.qa_repaint_key(2)
        self.assert_header_untouched();self.assertGreater(self.count(0,22,624,192),0)
    def test_status_progress_writes_only_footer(self):
        for h in (200,350,480):
            with self.subTest(height=h):
                self.prepare(h);self.lib.qa_repaint_progress(b'Receiving...')
                self.no_full_clear();self.assertEqual(self.count(0,0,640,h-8),0)
                self.assertGreater(self.count(0,h-8,640,h),0)
                self.reset();self.lib.qa_repaint_progress(b'Receiving...')
                self.assertEqual(self.count(0,0,640,h),0)
    def test_address_caret_and_typing_touch_only_address(self):
        self.prepare();self.lib.qa_repaint_key(3);self.reset()
        for k in (4,ord('x'),8):
            with self.subTest(key=k):
                self.lib.qa_repaint_key(k);self.no_full_clear()
                self.assertEqual(self.count(0,0,640,8),0)
                self.assertEqual(self.count(0,8,63,22),0)
                self.assertEqual(self.count(0,22,640,200),0)
                self.assertGreater(self.count(63,8,640,21),0);self.reset()
    def test_hover_updates_footer_only(self):
        self.prepare();self.lib.qa_repaint_hover(5,25)
        self.no_full_clear();self.assertEqual(self.count(0,0,640,192),0)
        self.assertGreater(self.count(0,192,640,200),0)
    def test_straddling_glyph_box_rule_clipped_from_chrome(self):
        for h in (200,350,480):
            with self.subTest(height=h):
                self.prepare(h,b'<u>Underline italic edge</u><p><i>Italic</i></p>'
                    b'<table border=1><tr><td>Box edge</td></tr></table><hr>'
                    b'<form><input name=q value=border><input type=checkbox checked>'
                    b'<input type=radio name=r checked><input type=submit value=Go>'
                    b'<select name=s><option>Chosen</option></select></form>'
                    b'<img src=missing.gif width=40 height=40 alt=Placeholder>')
                self.lib.qa_repaint_edges();self.assert_header_untouched()
                self.assertEqual(self.count(0,h-8,640,h),0)
    def test_editor_exit_repaints_highlight_without_frame(self):
        self.prepare();self.lib.qa_repaint_key(2);self.lib.qa_repaint_key(3);self.reset()
        self.lib.qa_repaint_key(5);self.no_full_clear()
        self.assertEqual(self.count(0,0,640,8),0)
        self.assertEqual(self.count(0,8,63,22),0)
        self.assertGreater(self.count(0,22,624,192),0)
    def test_failed_navigation_status_only_preserves_page(self):
        self.prepare();self.lib.qa_repaint_snapshot()
        self.assertEqual(self.lib.qa_repaint_load(b'file:/nonexistent-ew-repaint.htm'),0)
        self.no_full_clear();self.assertEqual(self.count(0,0,640,192),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,0,640,192),0)
        self.assertGreater(self.count(0,193,640,200),0)
    def test_failed_address_submit_exits_editor_without_frame_repaint(self):
        self.prepare();self.lib.qa_repaint_bad_address(b'file:/nonexistent-ew-repaint.htm')
        self.no_full_clear();self.assertEqual(self.count(0,0,640,8),0)
        self.assertEqual(self.count(0,8,63,22),0)
        self.assertGreater(self.count(63,8,640,21),0)
    def download(self):
        self.payload=b'BIN\0DATA'
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: 8\r\n\r\n'+self.payload)
        try:self.lib.qa_repaint_load((server.url+'/file.bin').encode())
        finally:server.close()
        self.assertEqual(self.lib.qa_repaint_download(),1)
    def test_download_progress_then_cancel_restores_page(self):
        self.prepare();self.lib.qa_repaint_snapshot();self.download();self.reset()
        self.lib.qa_repaint_progress(b'Saving file...')
        self.assertEqual(self.count(0,0,640,192),0)
        self.reset();self.lib.qa_repaint_key(5)
        self.no_full_clear();self.assertEqual(self.lib.qa_repaint_download(),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,22,624,192),0)
        self.assertEqual(self.count(0,8,63,22),0)
    def test_download_save_restores_page_and_exact_binary(self):
        self.prepare();self.lib.qa_repaint_snapshot();self.download();self.reset()
        with tempfile.TemporaryDirectory(prefix='ew-save-') as tmp:
            path=pathlib.Path(tmp)/'out.bin';self.lib.qa_repaint_save(os.fsencode(path))
            self.assertEqual(path.read_bytes(),self.payload)
        self.no_full_clear();self.assertEqual(self.lib.qa_repaint_download(),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,22,624,192),0)
        self.assertEqual(self.count(0,8,63,22),0)
    def test_mouse_back_from_address_editor_success_and_failure(self):
        for missing in (False,True):
            with self.subTest(failed_back=missing),tempfile.TemporaryDirectory(prefix='ew-back-') as tmp:
                self.prepare()
                first=pathlib.Path(tmp)/'first.htm';second=pathlib.Path(tmp)/'second.htm'
                first.write_text('<title>First</title><p>First history page</p>')
                second.write_text('<title>Second</title><p>Second history page</p>')
                self.assertEqual(self.lib.qa_repaint_load(('file:'+str(first)).encode()),1)
                self.assertEqual(self.lib.qa_repaint_load(('file:'+str(second)).encode()),1)
                if missing:first.unlink()
                self.lib.qa_repaint_key(3);self.lib.qa_repaint_key(ord('x'));self.reset()
                self.lib.qa_repaint_click_back();self.no_full_clear()
                self.assertEqual(self.count(0,8,63,22),0)
                self.assertEqual(self.lib.qa_repaint_editing(),0)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0,
                    'Incremental render differs from full rendering of actual UI state')
    def test_invert_and_chrome_toggle_still_repaint_full_view(self):
        for action in (6,7):
            with self.subTest(action=action):
                self.prepare();self.lib.qa_repaint_key(action)
                self.assertGreater(self.count(0,0,640,200),640*170)

if __name__=='__main__':unittest.main()
