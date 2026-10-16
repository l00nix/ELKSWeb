"""Control Unicode display, byte cursor boundaries and original-charset wire data."""
import ctypes as C
import unittest
import test_core_regression as core


def setUpModule():
    core.setUpModule()
    core.LIB.ew_display_text.argtypes=[C.c_char_p,C.c_void_p,C.c_uint,C.c_uint,C.c_int]
    core.LIB.ew_text_step.argtypes=[C.c_char_p,C.c_uint,C.c_int]


def tearDownModule():
    core.tearDownModule()


class FieldEncoding(unittest.TestCase):
    def display(self, value, cursor=0, password=False, cap=240):
        out=C.create_string_buffer(cap)
        caret=core.LIB.ew_display_text(value,out,cap,cursor,password)
        return out.value,caret

    def form(self, html, index=1):
        core.LIB.ew_parse(html,b'http://host/')
        url,post=C.create_string_buffer(768),C.create_string_buffer(768)
        self.assertEqual(core.LIB.ew_form_url(index,url,768,post,768),0)
        return url.value,post.value

    def test_display_expansion_and_byte_caret(self):
        value='Aé€ßZ'.encode()
        for cursor,offset in [(0,0),(1,1),(3,2),(6,5),(8,7),(9,8)]:
            self.assertEqual(self.display(value,cursor),(b'AeEURssZ',offset))

    def test_utf8_cursor_boundaries_both_directions(self):
        value='Aé€😀Z'.encode()
        boundaries=[0,1,3,6,10,11]
        for before,after in zip(boundaries,boundaries[1:]):
            self.assertEqual(core.LIB.ew_text_step(value,before,1),after)
            self.assertEqual(core.LIB.ew_text_step(value,after,-1),before)
        self.assertEqual(core.LIB.ew_text_step(value,0,-1),0)
        self.assertEqual(core.LIB.ew_text_step(value,11,1),11)

    def test_password_counts_characters_and_caret(self):
        self.assertEqual(self.display('AéB'.encode(),3,True),(b'***',2))

    def test_combining_mark_and_newline(self):
        self.assertEqual(self.display('e\u0301\nB'.encode(),3),(b'e B',1))

    def test_malformed_utf8_is_one_byte_unit(self):
        for value in [b'A\xc3B',b'A\x80B',b'A\xe0\x80\x80B',b'A\xf4\x90\x80\x80B']:
            self.assertEqual(core.LIB.ew_text_step(value,1,1),2)
            self.assertEqual(core.LIB.ew_text_step(value,2,-1),1)

    def test_legacy_name_value_and_entity_roundtrip(self):
        url,_=self.form(b'<meta charset=windows-1252><form action=/send>'
                       b'<input name="caf\xe9" value="caf\xe9 &#233; &#8364;">'
                       b'<input type=submit></form>')
        self.assertEqual(core.LIB.qa_link_value(0),'café é €'.encode())
        self.assertEqual(url,b'http://host/send?caf%E9=caf%E9+%E9+%80')
        self.assertEqual(self.display(core.LIB.qa_link_value(0))[0],b'cafe e EUR')

    def test_unrepresentable_legacy_entity_numeric_fallback(self):
        url,_=self.form(b'<meta charset=iso-8859-1><form><input name=q value="&#8364;">'
                       b'<input type=submit></form>')
        self.assertEqual(url,b'http://host/?q=%26%238364%3B')
        self.assertEqual(self.display(core.LIB.qa_link_value(0))[0],b'EUR')

    def test_undefined_legacy_bytes_preserved(self):
        url,_=self.form(b'<meta charset=windows-1252><form><input name=q value="\x81\x8d\x8f\x90\x9d">'
                       b'<input type=submit></form>')
        self.assertEqual(url,b'http://host/?q=%81%8D%8F%90%9D')

    def test_every_legacy_high_byte_roundtrips_on_wire(self):
        for charset in [b'iso-8859-1',b'iso-8859-2',b'windows-1252',b'windows-1250']:
            for byte in range(128,256):
                with self.subTest(charset=charset,byte=byte):
                    url,_=self.form(b'<meta charset='+charset+b'><form><input name=q value="'+bytes([byte])+b'">'
                                   b'<input type=submit></form>')
                    self.assertEqual(url,b'http://host/?q=%'+f'{byte:02X}'.encode())

    def test_select_textarea_hidden_submit_values(self):
        url,post=self.form(b'<meta charset=windows-1250><form method=post><select name=s>'
                          b'<option value="\x8a">caf\xe9</option></select>'
                          b'<textarea name=t>\x8a &#233;</textarea><input type=hidden name=h value="\xe9">'
                          b'<input type=submit name=b value="\x8a"></form>',3)
        self.assertEqual(core.LIB.ew_select_label(0,0),'café'.encode())
        self.assertEqual(self.display(core.LIB.qa_link_value(0))[0],b'cafe')
        self.assertEqual(post,b's=%8A&t=%8A+%E9&h=%E9&b=%8A')

    def test_meta_changes_do_not_reinterpret_existing_controls(self):
        url,_=self.form(b'<meta charset=windows-1252><form><input name=a value="\x8a">'
                       b'<meta charset=iso-8859-1><input name=b value="\x8a">'
                       b'<input type=submit></form>',2)
        self.assertEqual(url,b'http://host/?a=%8A&b=%8A')
        self.assertEqual(self.display(core.LIB.qa_link_value(0))[0],b'S')
        self.assertEqual(self.display(core.LIB.qa_link_value(1))[0],b'?')

    def test_utf8_attribute_capacity_preserves_whole_characters(self):
        for value,expected in [(b'a'*78+'é'.encode(),b'a'*78),
                               (b'a'*77+'é'.encode(),b'a'*77+'é'.encode()),
                               (b'a'*78+b'&#233;',b'a'*78)]:
            core.LIB.ew_parse(b'<input value="'+value+b'">',b'http://host/')
            self.assertEqual(core.LIB.qa_link_value(0),expected)

    def test_display_expansion_capacity_is_bounded(self):
        out=C.create_string_buffer(b'GUARD!',7)
        core.LIB.ew_display_text('€€'.encode(),out,4,6,0)
        self.assertEqual(out.raw,b'EUR\0D!\0')


if __name__=='__main__': unittest.main()
