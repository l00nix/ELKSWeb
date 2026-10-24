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
        cls.lib.qa_address_value.restype=C.c_char_p
        cls.lib.qa_address_status.restype=C.c_char_p
        cls.lib.qa_address_base.argtypes=[C.c_char_p]
        cls.lib.qa_repaint_writes.restype=C.c_ulong
        cls.lib.qa_repaint_outside_images.restype=C.c_ulong
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
        self.no_full_clear();self.assertEqual(self.count(0,0,640,32),0)
        self.assertEqual(self.count(624,32,625,self.height-12),0)
        self.assertEqual(self.count(639,32,640,self.height-12),0)
    def test_address_bar_defaults_to_http_and_preserves_request(self):
        for explicit in (False,True):
            self.prepare()
            server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<title>Typed URL</title>Loaded')
            url=server.url.replace('127.0.0.1','localhost')+'/path?q=hello'
            try:
                self.lib.qa_repaint_bad_address((url if explicit else url[7:]).encode())
            finally:server.close()
            self.assertTrue(server.request.startswith(b'GET /path?q=hello HTTP/1.0'))
            self.assertEqual(self.lib.qa_address_value(),url.encode())
    def test_address_bar_keeps_explicit_scheme_and_local_paths(self):
        self.prepare()
        self.lib.qa_repaint_bad_address(b'https://example.invalid/')
        self.assertEqual(self.lib.qa_address_value(),b'https://example.invalid/')
        with tempfile.NamedTemporaryFile(suffix='.htm') as page:
            page.write(b'<title>Local file</title>Local');page.flush()
            for prefix in ('','file:','file://'):
                self.prepare();self.lib.qa_address_base(b'')
                self.lib.qa_repaint_bad_address((prefix+page.name).encode())
                self.assertNotIn(b'http://',self.lib.qa_address_value())
                self.assertEqual(self.lib.qa_address_status(),b'')
    def test_address_bar_prefix_bounds_and_empty_input(self):
        self.prepare()
        value=b'x'*761
        self.lib.qa_repaint_bad_address(value)
        self.assertEqual(self.lib.qa_address_value(),value)
        self.assertEqual(self.lib.qa_address_status(),b'Address is too long')
        self.assertEqual(self.lib.qa_repaint_editing(),1)
        # Long but fitting address fails locally at unsupported URL port parsing,
        # avoiding a live DNS request while exercising the terminating NUL bound.
        value=b'127.0.0.1:bad/'+b'x'*(760-len(b'127.0.0.1:bad/'))
        self.lib.qa_repaint_bad_address(value)
        self.assertEqual(self.lib.qa_address_value(),b'http://'+value)
        self.assertEqual(self.lib.qa_repaint_editing(),0)
        with tempfile.NamedTemporaryFile(suffix='.htm') as page:
            page.write(b'<title>Empty address reload</title>Local');page.flush()
            self.lib.qa_address_base(page.name.encode())
            self.lib.qa_repaint_bad_address(b'')
            self.assertEqual(self.lib.qa_address_value(),page.name.encode())
            self.assertEqual(self.lib.qa_address_status(),b'')
    def test_scroll_never_writes_unchanged_chrome(self):
        for h in (200,350,480):
            with self.subTest(height=h):
                self.prepare(h);self.lib.qa_repaint_key(1)
                self.assert_header_untouched()
                self.assertGreater(self.count(0,32,624,h-12),0)
    def test_focus_page_highlight_keeps_title_address_frame(self):
        self.prepare();self.lib.qa_repaint_key(2)
        self.assert_header_untouched();self.assertGreater(self.count(0,32,624,188),0)
    def test_focus_repaints_only_link_band_and_matches_full_render(self):
        for h in (200,350,480):
            self.prepare(h)
            self.lib.qa_focus_step(1)
            self.assertEqual(self.count(0,60,640,h-12),0)
            self.assertEqual(self.count(624,32,640,h-12),0)
            self.assertLess(self.count(0,32,624,h-12),624*20)
            self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_focus_wrap_controls_tables_and_scrolling_match_full_render(self):
        html=(b'<table border=1><tr><td><a href="a">' + b'wrapped link '*50 +
              b'</a></td></tr></table><form><input name=q value="long field value">'
              b'<input type=password value=secret><input type=checkbox checked>'
              b'<input type=radio name=r checked><input type=radio name=r>'
              b'<select name=s><option>Alpha</option></select>'
              b'<textarea>multi line</textarea><input type=submit value=Go></form>'
              b'<p>spacing</p>'*20+b'<a href="last">Last</a>')
        for h in (200,350,480):
            self.prepare(h,html)
            for direction in [1]*12+[-1]*12:
                self.lib.qa_focus_step(direction)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
            self.lib.qa_repaint_key(6)
            for direction in (1,-1):
                self.lib.qa_focus_step(direction)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_empty_focus_editor_navigation_does_not_repaint_body(self):
        self.prepare()
        self.lib.qa_repaint_key(3)
        self.assertEqual(self.count(0,32,640,188),0)
        self.reset();self.lib.qa_repaint_key(5)
        self.assertEqual(self.count(0,32,640,188),0)
        self.reset();self.lib.qa_repaint_bad_address(b'file:/nonexistent-ew-repaint.htm')
        self.assertEqual(self.count(0,32,640,188),0)
        self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_mouse_navigation_does_not_repaint_unrelated_page_before_request(self):
        for height in (200,350,480):
            for kind in ('link','image','submit'):
                observed=[]
                def response(server):
                    observed.append(self.count(0,32,640,height-12))
                    return b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<title>Clicked</title>New document'
                server=OneHTTP(response)
                url=(server.url+'/clicked').encode()
                if kind=='submit':
                    html=b'<form action="'+url+b'"><input type=submit value=Go></form>'
                elif kind=='image':
                    html=b'<a href="'+url+b'"><img src="missing.gif" width=24 height=24></a>'
                else:html=b'<a href="'+url+b'">Click here</a>'
                try:
                    self.prepare(height,html+b'<p>Old content</p>')
                    self.lib.qa_repaint_click_link(0)
                finally:server.close()
                with self.subTest(height=height,kind=kind):
                    self.assertTrue(server.request.startswith(b'GET /clicked'))
                    self.assertEqual(observed,[0])
                    self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_mouse_focus_and_failed_navigation_preserve_unrelated_page(self):
        for height in (200,350,480):
            for html in (b'<a href="file:/nonexistent-ew-click.htm">Missing</a>',
                         b'<form><input name=q value=seed></form>'):
                self.prepare(height,html)
                self.lib.qa_repaint_click_link(0)
                self.assertEqual(self.count(0,90,624,height-12),0)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
                self.reset();self.lib.qa_repaint_click_link(-1)
                self.assertEqual(self.count(0,90,624,height-12),0)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_no_image_load_paints_document_once(self):
        for noimages in (0,1):
            self.prepare();self.lib.qa_focus_noimages(noimages)
            with tempfile.NamedTemporaryFile(suffix='.htm') as page:
                page.write(b'<p>A new document</p>');page.flush()
                self.assertEqual(self.lib.qa_repaint_load(('file:'+page.name).encode()),1)
            # Empty interior has exactly one background write, not two paints.
            self.assertEqual(self.count(0,100,624,120),624*20)
            self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
        self.lib.qa_focus_noimages(0)
    def test_status_progress_writes_only_footer(self):
        for h in (200,350,480):
            with self.subTest(height=h):
                self.prepare(h);self.lib.qa_repaint_progress(b'Receiving...')
                self.no_full_clear();self.assertEqual(self.count(0,0,640,h-12),0)
                self.assertGreater(self.count(0,h-12,640,h),0)
                self.reset();self.lib.qa_repaint_progress(b'Receiving...')
                self.assertEqual(self.count(0,0,640,h),0)

    def image_page(self, html, height=200, fragment=''):
        self.prepare(height)
        self.lib.qa_focus_noimages(0)
        with tempfile.NamedTemporaryFile(suffix='.htm') as page:
            page.write(html);page.flush()
            self.assertEqual(self.lib.qa_repaint_load(
                ('file:'+page.name+fragment).encode()),1)

    def test_sized_images_leave_surrounding_page_painted(self):
        image=os.fsencode(ROOT/'tests/fixtures/image.gif')
        for height in (200,350,480):
            for extra in (b'',b'<a href="/next">',b'<table border=1><tr><td>'):
                with self.subTest(height=height,extra=extra):
                    html=(b'<title>Images</title><p>Before</p>'+extra+
                          b'<img src="'+image+b'" width=40 height=32 alt=Placeholder>'+
                          b'</a></td></tr></table><p>After</p>')
                    self.image_page(html,height)
                    self.assertEqual(self.lib.qa_scroll_loaded_images(),1)
                    # Blank body pixels are cleared once, never again for images.
                    self.assertEqual(self.count(0,height-38,624,height-18),624*20)
                    self.assertEqual(self.lib.qa_repaint_reparse_equivalence(),0)

    def test_failed_sized_image_keeps_placeholder_without_second_page_paint(self):
        self.image_page(b'<p>Before</p><img src=/missing-ew.gif width=40 height=20 alt=Missing>')
        self.assertEqual(self.lib.qa_scroll_loaded_images(),0)
        self.assertEqual(self.count(0,100,624,120),624*20)
        self.assertEqual(self.lib.qa_repaint_reparse_equivalence(),0)

    def test_image_update_writes_only_rectangles_including_transparency(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'transparent.gif'
            im=Image.new('P',(16,16),0)
            im.putpalette([255,255,255,0,0,0]+[0]*762)
            for y in range(4,12):
                for x in range(4,12):im.putpixel((x,y),1)
            im.save(path,transparency=0)
            image=os.fsencode('file:'+str(path))
            html=(b'<p>Keep text</p><center><img src="'+image+
                  b'" width=40 height=32 alt=EraseMe></center>'
                  b'<table border=1><tr><td>Cell<img src="'+image+
                  b'" width=60 height=50 alt=EraseToo></td></tr></table><p>After</p>')
            for height in (200,350,480):
                for inverted in (False,True):
                    self.prepare(height,html)
                    if inverted:self.lib.qa_repaint_key(6)
                    self.reset();self.lib.qa_repaint_complete_images()
                    self.assertEqual(self.lib.qa_scroll_loaded_images(),2)
                    self.assertEqual(self.lib.qa_repaint_outside_images(),0)
                    self.assertGreater(self.count(0,32,624,height-12),0)
                    self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)

    def test_image_updates_clip_at_viewport_edges(self):
        image=os.fsencode('file:'+str(ROOT/'tests/fixtures/frogfind/frog.gif'))
        for height in (200,350,480):
            html=(b'<img src="'+image+b'" width=174 height=80>'+
                  b'<p>Unchanged text</p>'*35+
                  b'<img src="'+image+b'" width=174 height=80>')
            for scroll in (10,120):
                self.prepare(height,html)
                self.lib.qa_scroll_move(scroll);self.lib.qa_scroll_flush()
                self.reset();self.lib.qa_repaint_complete_images()
                self.assertEqual(self.lib.qa_repaint_outside_images(),0)
                self.assertEqual(self.count(0,0,640,32),0)
                self.assertEqual(self.count(0,height-12,640,height),0)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)

    def test_image_dimensions_reflow_when_either_attribute_is_missing(self):
        image=os.fsencode(ROOT/'tests/fixtures/frogfind/frog.gif')
        for attrs in (b'',b'width=80',b'height=120'):
            for height in (200,350,480):
                with self.subTest(attrs=attrs,height=height):
                    self.image_page(b'<p>Before</p><img src="'+image+b'" '+attrs+
                                    b'><p>After image</p>',height)
                    self.assertEqual(self.lib.qa_scroll_loaded_images(),1)
                    self.assertEqual(self.lib.qa_repaint_reparse_equivalence(),0)

    def test_image_completion_fragment_scroll_matches_reflow(self):
        image=os.fsencode(ROOT/'tests/fixtures/image.gif')
        html=(b'<img src="'+image+b'" width=40 height=32>'+b'<p>Line</p>'*35+
              b'<a name=destination></a><p>Target</p><img src="'+image+
              b'" width=80 height=64>')
        for height in (200,350,480):
            self.image_page(html,height,'#destination')
            self.assertGreater(self.lib.qa_scroll_position(),0)
            self.assertEqual(self.lib.qa_repaint_reparse_equivalence(),0)
    def test_address_caret_and_typing_touch_only_address(self):
        self.prepare();self.lib.qa_repaint_key(3);self.reset()
        for k in (4,ord('x'),8):
            with self.subTest(key=k):
                self.lib.qa_repaint_key(k);self.no_full_clear()
                self.assertEqual(self.count(0,0,640,13),0)
                self.assertEqual(self.count(0,14,63,32),0)
                self.assertEqual(self.count(0,32,640,200),0)
                self.assertGreater(self.count(63,14,640,31),0);self.reset()
    def test_hover_updates_footer_only(self):
        self.prepare();self.lib.qa_repaint_hover(5,35)
        self.no_full_clear();self.assertEqual(self.count(0,0,640,188),0)
        self.assertGreater(self.count(0,188,640,200),0)
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
                self.assertEqual(self.count(0,h-12,640,h),0)
    def test_editor_exit_repaints_highlight_without_frame(self):
        self.prepare();self.lib.qa_repaint_key(2);self.lib.qa_repaint_key(3);self.reset()
        self.lib.qa_repaint_key(5);self.no_full_clear()
        self.assertEqual(self.count(0,0,640,13),0)
        self.assertEqual(self.count(0,14,63,32),0)
        self.assertGreater(self.count(0,32,624,188),0)
    def test_failed_navigation_status_only_preserves_page(self):
        self.prepare();self.lib.qa_repaint_snapshot()
        self.assertEqual(self.lib.qa_repaint_load(b'file:/nonexistent-ew-repaint.htm'),0)
        self.no_full_clear();self.assertEqual(self.count(0,0,640,188),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,0,640,188),0)
        self.assertGreater(self.count(0,189,640,200),0)
    def test_failed_address_submit_exits_editor_without_frame_repaint(self):
        self.prepare();self.lib.qa_repaint_bad_address(b'file:/nonexistent-ew-repaint.htm')
        self.no_full_clear();self.assertEqual(self.count(0,0,640,13),0)
        self.assertEqual(self.count(0,14,63,32),0)
        self.assertGreater(self.count(63,14,640,31),0)
    def download(self):
        self.payload=b'BIN\0DATA'
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: 8\r\n\r\n'+self.payload)
        try:self.lib.qa_repaint_load((server.url+'/file.bin').encode())
        finally:server.close()
        self.assertEqual(self.lib.qa_repaint_download(),1)
    def test_download_progress_then_cancel_restores_page(self):
        self.prepare();self.lib.qa_repaint_snapshot();self.download();self.reset()
        self.lib.qa_repaint_progress(b'Saving file...')
        self.assertEqual(self.count(0,0,640,188),0)
        self.reset();self.lib.qa_repaint_key(5)
        self.no_full_clear();self.assertEqual(self.lib.qa_repaint_download(),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,32,624,188),0)
        self.assertEqual(self.count(0,14,63,32),0)
    def test_download_save_restores_page_and_exact_binary(self):
        self.prepare();self.lib.qa_repaint_snapshot();self.download();self.reset()
        with tempfile.TemporaryDirectory(prefix='ew-save-') as tmp:
            path=pathlib.Path(tmp)/'out.bin';self.lib.qa_repaint_save(os.fsencode(path))
            self.assertEqual(path.read_bytes(),self.payload)
        self.no_full_clear();self.assertEqual(self.lib.qa_repaint_download(),0)
        self.assertEqual(self.lib.qa_repaint_difference(0,32,624,188),0)
        self.assertEqual(self.count(0,14,63,32),0)
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
                self.assertEqual(self.count(0,14,63,32),0)
                self.assertEqual(self.lib.qa_repaint_editing(),0)
                self.assertEqual(self.lib.qa_repaint_full_equivalence(),0,
                    'Incremental render differs from full rendering of actual UI state')
    def test_invert_and_chrome_toggle_still_repaint_full_view(self):
        for action in (6,7):
            with self.subTest(action=action):
                self.prepare();self.lib.qa_repaint_key(action)
                self.assertGreater(self.count(0,0,640,200),640*170)

if __name__=='__main__':unittest.main()
