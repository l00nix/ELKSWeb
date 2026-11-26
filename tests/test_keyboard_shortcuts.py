"""Exercise actual browser dispatch, framebuffer, local help and HTTP reload."""
import ctypes as C
from pathlib import Path
import tempfile
import unittest
import test_repaint_regions as repaint
from test_core_regression import OneHTTP


class Shortcuts:
    @classmethod
    def setUpClass(cls):
        cls.helpdir = tempfile.TemporaryDirectory(prefix='ew-help-')
        cls.helpfile = Path(cls.helpdir.name) / 'keys.htm'
        cls.helpfile.write_bytes((repaint.ROOT/'share/keys.htm').read_bytes())
        cls.defines = list(getattr(cls, 'backend', [])) + [f'-DEW_HELP_PAGE="{cls.helpfile}"']
        repaint.RepaintRegions.setUpClass.__func__(cls)
        cls.lib.qa_field_value.restype = C.c_char_p
        cls.lib.qa_download_filename.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        repaint.RepaintRegions.tearDownClass.__func__(cls)
        cls.helpdir.cleanup()

    setUp = repaint.RepaintRegions.setUp
    tearDown = repaint.RepaintRegions.tearDown
    prepare = repaint.RepaintRegions.prepare

    def ctrl(self, letter):
        self.lib.qa_shortcut(ord(letter.upper()) & 31)

    def test_redraw_restores_pixels_without_reload_or_losing_form_edits(self):
        self.prepare(html=b'<form><input name=q value=seed></form>')
        self.ctrl('n')
        self.lib.qa_shortcut(ord('X'))
        value = self.lib.qa_field_value()
        url = self.lib.qa_current_url()
        self.lib.qa_repaint_snapshot()
        self.lib.qa_shortcut_stale_pixel()
        self.ctrl('d')
        self.assertEqual(self.lib.qa_repaint_difference(0,0,640,200), 0)
        self.assertEqual(self.lib.qa_field_value(), value)
        self.assertEqual(self.lib.qa_current_url(), url)
        self.assertEqual(self.lib.qa_address_status(), b'')

    def test_themes_bars_and_reserved_tab_backspace(self):
        self.prepare()
        self.ctrl('v'); self.assertEqual(self.lib.qa_shortcut_inverse(), 1)
        self.ctrl('v'); self.assertEqual(self.lib.qa_shortcut_inverse(), 0)
        self.ctrl('t'); self.assertEqual(self.lib.qa_shortcut_chrome(), 0)
        self.ctrl('l'); self.assertEqual(self.lib.qa_shortcut_chrome(), 1)
        self.lib.qa_shortcut(ord('x'))
        self.ctrl('h'); self.assertEqual(self.lib.qa_address_value(), b'')
        self.lib.qa_shortcut(27)
        self.ctrl('i'); self.assertEqual(self.lib.qa_shortcut_focus(), 0)
        self.ctrl('n'); self.assertEqual(self.lib.qa_shortcut_focus(), 1)
        self.ctrl('w'); self.assertEqual(self.lib.qa_shortcut_focus(), 0)

    def test_help_from_http_is_local_and_history_returns_to_original(self):
        self.prepare()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'original.htm';f.write_text('<title>Original</title>Original')
            self.assertEqual(self.lib.qa_repaint_load(('file:'+str(f)).encode()), 1)
            self.ctrl('g')
            self.assertIn(b'keys.htm', self.lib.qa_current_url())
            self.assertNotIn(b'http:', self.lib.qa_current_url())
            self.ctrl('b');self.assertIn(b'original.htm', self.lib.qa_current_url())
            self.ctrl('f');self.assertIn(b'keys.htm', self.lib.qa_current_url())
        # The initial fixture uses an HTTP base: help must still be a local file.
        self.prepare();self.ctrl('g')
        self.assertNotIn(b'http:', self.lib.qa_current_url())
        self.assertEqual(self.lib.qa_address_status(), b'')

    def test_missing_help_preserves_current_page(self):
        self.prepare();url=self.lib.qa_current_url()
        hidden=self.helpfile.with_suffix('.bak');self.helpfile.rename(hidden)
        try:
            self.ctrl('g')
            self.assertEqual(self.lib.qa_current_url(), url)
            self.assertIn(b'help missing', self.lib.qa_address_status())
        finally:hidden.rename(self.helpfile)

    def test_reload_requests_same_http_url_without_growing_history(self):
        page=b'<title>Reload</title>Hello'
        response=b'HTTP/1.0 200 OK\r\nContent-Length: '+str(len(page)).encode()+b'\r\n\r\n'+page
        server=OneHTTP([response,response])
        try:
            self.prepare();self.lib.qa_repaint_load(server.url.encode())
            history=self.lib.qa_shortcut_history()
            self.ctrl('d')
            self.assertEqual(len(server.requests),1)
            self.ctrl('r')
            self.assertEqual(len(server.requests),2)
            self.assertEqual(server.requests[0],server.requests[1])
            self.assertEqual(self.lib.qa_shortcut_history(),history)
        finally:server.close()

    def test_navigation_shortcuts_do_not_discard_address_or_download_edits(self):
        self.prepare();self.ctrl('l');self.lib.qa_shortcut(ord('x'))
        for letter in 'rgbf':self.ctrl(letter)
        self.assertEqual(self.lib.qa_address_value(),b'x')
        self.assertTrue(self.lib.qa_repaint_editing())
        self.ctrl('d');self.assertEqual(self.lib.qa_address_value(),b'x')
        self.lib.qa_shortcut(27)
        repaint.RepaintRegions.download(self)
        name=self.lib.qa_download_filename()
        for letter in 'rgbf':self.ctrl(letter)
        self.ctrl('d')
        self.assertTrue(self.lib.qa_repaint_download())
        self.assertEqual(self.lib.qa_download_filename(),name)
        self.ctrl('l');self.assertFalse(self.lib.qa_repaint_download())
        self.assertTrue(self.lib.qa_repaint_editing())



class DirectShortcuts(Shortcuts, unittest.TestCase):pass
class NanoXShortcuts(Shortcuts, unittest.TestCase):backend=['-DELKSWEB_NANOX']
if __name__ == '__main__':unittest.main()
