"""Bounded flat-table negotiation and complete parser replay ownership."""
import ctypes as C
from pathlib import Path
import random
import unittest
import test_table_wrap as wrap

PHRASE='One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen.'
LONG='<table border=1 width=180><tr><td>Label</td><td>'+PHRASE+'</td></tr></table>'


class AutomaticTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wrap.TableWrap.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        wrap.TableWrap.tearDownClass.__func__(cls)

    parse=wrap.TableWrap.parse
    texts=wrap.TableWrap.texts
    boxes=wrap.TableWrap.boxes
    textwidth=wrap.TableWrap.textwidth
    text_extent=wrap.TableWrap.text_extent

    def test_probe_targets_and_link_identity(self):
        self.parse((Path(__file__).parent/'fixtures/auto-columns.htm').read_text())
        self.assertEqual([r['width'] for r in self.boxes()],[35,239,35,239,280,325,293,624])
        linked=[r for r in self.texts() if self.lib.qa_run_link(r['i'])]
        self.assertEqual(len(linked),2)
        self.assertTrue(all(self.lib.qa_run_link(r['i'])==1 for r in linked))
        self.assertEqual(self.lib.qa_links(),1)
        self.assertFalse(self.lib.qa_truncated())


    def test_mixed_style_unbroken_word_sets_one_minimum(self):
        self.parse('<table border=1 width=30><td>Super<b>cali</b><i>fragilistic</i></td><td>x</table>')
        texts=self.texts()[:-1]
        self.assertEqual(len({r['y'] for r in texts}),1)
        self.assertGreater(self.boxes()[-1]['width'],30)
        self.assertEqual(self.boxes()[0]['width'],sum(self.textwidth(r) for r in texts)+4)


    def test_controls_images_and_pre_cannot_be_shrunk_away(self):
        for item,kind in [('<input name=q value=hello>',2),('<img src=/x width=212 height=20>',5),
                          ('<pre>one  two  three  four</pre>',0)]:
            self.parse('<table border=1 width=180><td>'+item+'</td><td>'+PHRASE+'</table>')
            if kind:
                intrinsic=next(r for r in self.runs if r['kind']==kind)
                width=self.lib.qa_run_width_field(intrinsic['i']) if kind==2 else intrinsic['width']
            else:
                pre=[r for r in self.texts() if r['style']&64]
                self.assertEqual(len({r['y'] for r in pre}),1)
                width=self.text_extent(pre)
            self.assertGreaterEqual(self.boxes()[0]['width'],width+4)
            self.assertTrue(all(0<=r['x']<=16000 for r in self.runs))


    def test_anchor_rebuilt_after_wrapping(self):
        self.parse(LONG+'<p id=target>Target text</p>')
        target=next(r for r in self.texts() if r['text']==b'Target text')
        self.lib.ew_anchor_y.argtypes=[C.c_char_p]
        self.assertEqual(self.lib.ew_anchor_y(b'target'),target['y'])
        self.assertGreater(target['y'],30)


    def test_charset_and_successful_controls_rebuilt_once(self):
        html=('<form action=/send method=post><input name=q value="é">'+LONG+
              '<meta charset=windows-1250><input name=r value="').encode()+b'\x8a'+(
              '"><select name=s><option value=a>A</option><option selected value=b>B</select>'
              '<input type=submit name=go value=Yes></form>').encode()
        self.lib.ew_parse(html,b'http://host/')
        self.assertEqual(self.lib.qa_links(),4)
        self.assertEqual(self.lib.ew_select_count(2),2)
        self.assertEqual(self.lib.ew_select_index(2),1)
        url,post=C.create_string_buffer(768),C.create_string_buffer(768)
        self.assertEqual(self.lib.ew_form_url(3,url,768,post,768),0)
        self.assertEqual(post.value,b'q=%C3%A9&r=%8A&s=b&go=Yes')


    def test_file_source_replay_restores_mime_charset(self):
        html=b'<form method=post><input name=q value="caf\xe9">'+LONG.encode()+b'<meta charset=utf-8><input type=submit></form>'
        self.lib.ew_source_put.argtypes=[C.c_uint32,C.c_ubyte]
        self.lib.ew_source_finish.argtypes=[C.c_uint32]
        self.lib.ew_parse_source.argtypes=[C.c_char_p]
        self.assertEqual(self.lib.ew_source_begin(),0)
        for offset,byte in enumerate(html): self.assertEqual(self.lib.ew_source_put(offset,byte),0)
        self.assertEqual(self.lib.ew_source_finish(len(html)),0)
        C.c_ubyte.in_dll(self.lib,'ew_document_charset').value=2
        self.lib.ew_parse_source(b'http://host/')
        url,post=C.create_string_buffer(768),C.create_string_buffer(768)
        self.assertEqual(self.lib.ew_form_url(1,url,768,post,768),0)
        self.assertEqual(post.value,b'q=caf%E9')
        self.assertEqual(C.c_ubyte.in_dll(self.lib,'ew_document_charset').value,2)


    def test_spans_nesting_and_unclosed_tables_keep_fallback(self):
        for html in ['<table border=1 width=100><td colspan=2>'+PHRASE+'</table>',
                     '<table border=1 width=100><td rowspan=2>'+PHRASE+'</table>',
                     '<table border=1 width=100><td>'+PHRASE+'<table><td>inner</table></table>',
                     '<table border=1 width=100><td>'+PHRASE]:
            self.parse(html)
            self.assertGreater(self.boxes()[-1]['width'],500)


    def test_sixteen_plan_limit_falls_back_without_warning(self):
        self.parse(LONG*17)
        outer=self.boxes()[2::3]
        self.assertEqual(len(outer),17)
        self.assertTrue(all(r['width']==180 for r in outer[:16]))
        self.assertGreater(outer[-1]['width'],500)
        self.assertFalse(self.lib.qa_truncated())


    def test_truncated_measurement_is_not_replayed(self):
        self.parse(LONG+''.join('<a href=/x>'+str(i)+'</a><br>' for i in range(300)))
        self.assertTrue(self.lib.qa_truncated())
        self.assertGreater(self.boxes()[2]['width'],500)


    def test_reflow_capacity_recovers_complete_original_and_identities(self):
        row='<tr><td><a href=/next>'+PHRASE+'</a></td></tr>'
        html=('<form method=post><input name=q value="é">'+
              ('<table width=100>'+row*15+'</table>')*12+
              '<p id=target>ENDMARKER</p><meta charset=windows-1250>'
              '<input name=r value="').encode()+b'\x8a'+b'"><input type=submit></form>'
        self.lib.ew_parse(html,b'http://host/')
        self.assertFalse(self.lib.qa_truncated())
        self.assertEqual(self.lib.qa_links(),183)
        self.assertEqual(self.lib.qa_runs(),184)
        matches=[]
        for i in range(self.lib.qa_runs()):
            if self.lib.qa_run_kind(i)==0:
                text=C.string_at(self.lib.qa_run_data(i),self.lib.qa_run_length(i))
                if text==b'ENDMARKER': matches.append(i)
        self.assertEqual(len(matches),1)
        self.lib.ew_anchor_y.argtypes=[C.c_char_p]
        self.assertEqual(self.lib.ew_anchor_y(b'target'),self.lib.qa_y(matches[0]))
        url,post=C.create_string_buffer(768),C.create_string_buffer(768)
        self.assertEqual(self.lib.ew_form_url(182,url,768,post,768),0)
        self.assertEqual(post.value,b'q=%C3%A9&r=%8A')

    def test_zero_huge_and_empty_requested_tables(self):
        for value in ['0','1','999999999999','100%']:
            self.parse('<table border=1 width='+value+'><tr><td>'+PHRASE+'</td><td>peer</table>')
            self.assertTrue(all(0<=r['x']<=16000 and 0<=r['y']<=16000 for r in self.runs))
            self.assertEqual(b''.join(r['text'] for r in self.texts()).replace(b' ',b''),(PHRASE+'peer').encode().replace(b' ',b''))
        self.parse('<table border=1 width=100></table>')
        self.assertFalse(self.lib.qa_truncated())


    def test_bounded_malformed_replay(self):
        rng=random.Random(2168088)
        tokens=['<table border=1 width=180>','<table border=1>','</table>','<tr>','</tr>','<td>','</td>',
                '<td width=50>','<td colspan=2>','<td rowspan=2>','<b>','</b>','<pre>','</pre>',
                '<form>','</form>','<input name=q value=x>','<a href=/x>','</a>',PHRASE,'<br>',
                '<meta charset=windows-1250>','<meta charset=utf-8>']
        for case in range(1000):
            self.parse(''.join(rng.choice(tokens) for _ in range(rng.randrange(1,70))))
            self.assertTrue(all(0<=r['x']<=16000 and 0<=r['y']<=16000 for r in self.runs),case)
            self.assertLessEqual(len(self.runs),1024)

if __name__=='__main__':unittest.main()
