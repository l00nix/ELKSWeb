"""Issue #7: editing must change the control without repainting the page.

Uses actual main.c key handlers/fonts/parser, counts every framebuffer write,
and checks incremental pixels against a complete repaint in both compile paths.
"""
import ctypes as C
import unittest
import test_repaint_regions as repaint
from test_core_regression import OneHTTP

class FieldEditing:
    @classmethod
    def setUpClass(cls):
        repaint.RepaintRegions.setUpClass.__func__(cls)
        cls.lib.qa_field_value.restype=C.c_char_p
    @classmethod
    def tearDownClass(cls):repaint.RepaintRegions.tearDownClass.__func__(cls)
    setUp=repaint.RepaintRegions.setUp
    tearDown=repaint.RepaintRegions.tearDown
    prepare=repaint.RepaintRegions.prepare
    reset=repaint.RepaintRegions.reset
    count=repaint.RepaintRegions.count
    def focus(self):
        self.lib.qa_focus_step(1)
        self.lib.qa_field_key(3)
    def edit(self,key,value,pos):
        self.reset();lo=self.lib.qa_field_band(0);hi=self.lib.qa_field_band(1)
        self.lib.qa_field_key(key)
        self.assertEqual(self.lib.qa_field_value(),value)
        self.assertEqual(self.lib.qa_field_position(),pos)
        self.assertEqual(self.count(0,0,640,lo),0)
        self.assertEqual(self.count(0,hi,640,self.height),0)
        self.assertEqual(self.count(624,lo,640,hi),0)
        self.assertGreater(self.count(0,lo,624,hi),0)
        self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_all_edit_paths_repaint_only_field_band(self):
        for height in (200,350,480):
            for tag in (b'<input name=q value=seed>',b'<input type=password name=q value=seed>',b'<textarea name=q>seed</textarea>'):
                with self.subTest(height=height,tag=tag):
                    self.prepare(height,b'<p>Above</p><form>'+tag+b'</form><p>Below stays still</p>');self.focus()
                    for key,value,pos in [(ord('x'),b'seedx',5),(0,b'seedx',4),(1,b'seedx',5),(2,b'seedx',0),(5,b'eedx',0),(3,b'eedx',4),(4,b'eed',3),(3,b'eed',3),(5,b'eed',3),(2,b'eed',0),(4,b'eed',0)]:self.edit(key,value,pos)
    def test_long_field_scroll_and_focus_transitions(self):
        self.prepare(480,b'<form><input name=q size=5 value="'+b'x'*60+b'"><input name=r value=next></form><p>Unaffected</p>');self.focus()
        self.edit(2,b'x'*60,0);self.edit(ord('A'),b'A'+b'x'*60,1);self.edit(3,b'A'+b'x'*60,61)
        self.lib.qa_field_key(9);self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
        self.assertEqual(self.lib.qa_field_value(),b'next')
    def test_utf8_caret_and_deletion(self):
        self.prepare(200,'<form><input name=q value="café"></form><p>Below</p>'.encode());self.focus()
        self.edit(0,'café'.encode(),3);self.edit(5,b'caf',3);self.edit(2,b'caf',0);self.edit(ord('X'),b'Xcaf',1)
    def test_pending_scroll_keeps_full_redraw_fallback(self):
        self.prepare(200,b'<p>Above</p><form><input name=q value=seed></form>'+b'<p>Line</p>'*40);self.focus();self.reset()
        self.lib.qa_scroll_move(10);self.lib.qa_field_key(ord('x'))
        self.assertEqual(self.lib.qa_field_value(),b'seedx')
        self.assertGreater(self.count(0,100,624,180),0)
        self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_edited_value_submits_over_http(self):
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<title>Submitted</title>Result')
        try:
            self.prepare(480,b'<form action="'+server.url.encode()+b'/search"><input name=q value=seed><input type=submit value=Go></form>');self.focus()
            self.edit(ord('x'),b'seedx',5);self.lib.qa_field_key(6)
        finally:server.close()
        self.assertTrue(server.request.startswith(b'GET /search?q=seedx HTTP/1.0'),server.request)
        self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)

class DirectFieldEditing(FieldEditing,unittest.TestCase):pass
class NanoXFieldEditing(FieldEditing,unittest.TestCase):defines=['-DELKSWEB_NANOX=1']
