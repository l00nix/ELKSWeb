"""Explicit cell bounds: readable word wrapping with intrinsic item overflow."""
import ctypes as C
import random
import unittest
import test_tables as tables


class TableWrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tables.Tables.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        tables.Tables.tearDownClass.__func__(cls)

    def parse(self, html):
        return tables.Tables.parse(self, html)

    def texts(self):
        return tables.Tables.texts(self)

    def boxes(self):
        return tables.Tables.boxes(self)

    def textwidth(self, run):
        style=run['style']
        name=('ew_mono_width' if style&64 else 'ew_small_width' if style&32
              else 'ew_font_width' if style&4 else 'ew_body_width')
        fn=getattr(self.lib,name)
        args=[run['text'],len(run['text']),bool(style&1)]
        if style&64: args.append(0 if style&32 else 2 if style&4 else 1)
        return fn(*args)

    def text_extent(self, runs):
        left=min(r['x'] for r in runs)
        return max(r['x']+self.textwidth(r) for r in runs)-left

    def test_fixed_cell_wraps_phrase_with_padding(self):
        self.parse('<table border=1><td width=60>one two three four five six</td><td>Peer</table>')
        lines=[r for r in self.texts() if r['text']!=b'Peer']
        self.assertGreater(len({r['y'] for r in lines}),1)
        self.assertLessEqual(self.text_extent(lines),56)
        self.assertEqual(self.boxes()[0]['width'],60)
        self.assertEqual(self.texts()[-1]['x'],66)
        self.assertEqual(b''.join(r['text'] for r in lines).replace(b' ',b''),b'onetwothreefourfivesix')

    def test_percent_cell_uses_requested_table_width(self):
        self.parse('<table border=1 width=240><td width="50%">'+('one two three '*8)+'</table>')
        self.assertGreater(len(self.texts()),1)
        self.assertLessEqual(self.text_extent(self.texts()),116)
        self.assertEqual(self.boxes()[-1]['width'],240)

    def test_padding_reduces_content_bound(self):
        counts=[]
        for padding in [0,15]:
            self.parse('<table border=1 cellpadding='+str(padding)+'><td width=100>'+('one two three '*8)+'</table>')
            self.assertLessEqual(self.text_extent(self.texts()),100-2*padding)
            counts.append(len({r['y'] for r in self.texts()}))
        self.assertGreater(counts[1],counts[0])

    def test_unbreakable_word_expands_tiny_cell(self):
        word='Supercalifragilistic'
        self.parse('<table border=1><td width=1>'+word+'</table>')
        self.assertEqual([r['text'] for r in self.texts()],[word.encode()])
        self.assertEqual(self.boxes()[0]['width'],self.textwidth(self.texts()[0])+4)

    def test_exceptionally_long_word_keeps_viewport_split(self):
        self.parse('<table border=1><td width=1>'+('W'*250)+'</table>')
        self.assertGreater(len(self.texts()),1)
        self.assertEqual(b''.join(r['text'] for r in self.texts()),b'W'*250)
        self.assertLessEqual(self.text_extent(self.texts()),624)

    def test_zero_missing_and_large_width_keep_viewport_flow(self):
        phrase='one two three '*20
        for width in ['', ' width=0', ' width=16000', ' width=9999999999999999']:
            self.parse('<table border=1><td'+width+'>'+phrase+'</table>')
            self.assertGreater(self.text_extent(self.texts()),500)
            self.assertLessEqual(self.text_extent(self.texts()),624)
            self.assertEqual(b''.join(r['text'] for r in self.texts()).replace(b' ',b''),phrase.encode().replace(b' ',b''))

    def test_large_padding_and_nested_list_cannot_stall(self):
        self.parse('<table border=1 cellpadding=64><td width=1>'+'<ul><li>'*12+'one two three'+'</ul>'*12+'</table>')
        self.assertEqual(b''.join(r['text'] for r in self.texts()).replace(b' ',b''),b'onetwothree')
        self.assertTrue(all(0<=r['x']<=16000 and 0<=r['y']<=16000 for r in self.runs))

    def test_styles_and_link_identity_survive_wrap(self):
        self.parse('<table><th width=70>one two <i>three four</i> <a href=/next>five six seven eight</a></table>')
        self.assertTrue(all(r['style']&1 for r in self.texts()))
        self.assertTrue(any(r['style']&16 for r in self.texts()))
        linked=[r for r in self.texts() if self.lib.qa_run_link(r['i'])]
        self.assertGreater(len({r['y'] for r in linked}),1)
        self.assertTrue(all(self.lib.qa_run_link(r['i'])==1 for r in linked))
        self.assertLessEqual(self.text_extent(self.texts()),66)

    def test_forms_and_images_keep_intrinsic_width_but_start_new_line(self):
        for item,kind in [('<form><input value=hello></form>',2),('<img src=/x.gif width=120 height=20>',5)]:
            self.parse('<table border=1><td width=60>Text'+item+'tail words end</table>')
            intrinsic=next(r for r in self.runs if r['kind']==kind)
            self.assertGreater(intrinsic['y'],self.texts()[0]['y'])
            self.assertGreater(self.boxes()[0]['width'],60)
            self.assertGreater(self.texts()[-1]['y'],intrinsic['y'])

    def test_preformatted_line_expands_cell_without_reflow(self):
        line='one  two  three  four  five'
        self.parse('<table border=1><td width=60><pre>'+line+'</pre></table>')
        self.assertEqual(b''.join(r['text'] for r in self.texts()),line.encode())
        self.assertEqual(len({r['y'] for r in self.texts()}),1)
        self.assertGreater(self.boxes()[0]['width'],60)

    def test_nested_cell_bound_restores_outer_and_following_page(self):
        self.parse('<table><td width=100>outer one two three four five'
                   '<table><td width=40><i>inner one two three four</i></table>'
                   '<b>after one two three four five</b></table>outside one two three four five')
        normal=[r for r in self.texts() if not r['style'] and not r['text'].startswith(b'outside')]
        inner=[r for r in self.texts() if r['style']&16]
        after=[r for r in self.texts() if r['style']&1]
        self.assertLessEqual(self.text_extent(normal),96)
        self.assertLessEqual(self.text_extent(inner),36)
        self.assertLessEqual(self.text_extent(after),96)
        outside=[r for r in self.texts() if r['text'].startswith(b'outside')]
        self.assertEqual(len(outside),1)
        self.assertGreater(self.textwidth(outside[0]),100)

    def test_malformed_random_explicit_widths_are_bounded(self):
        rng=random.Random(8188)
        tags=['<table border=1>','<table cellpadding=64 width=1>','</table>','<tr>','</tr>',
              '<td width=1>','<td width=0>','<td width="20%">','<th width=40 colspan=2>',
              '</td>','</th>','<ul><li>','</ul>','<pre>','</pre>','<b>','</b>',
              '<font size=7>','</font>','word words ','W'*200,'<input value=x>',
              '<img src=/x width=60 height=20>','<br>']
        for case in range(1000):
            self.parse(''.join(rng.choice(tags) for _ in range(rng.randrange(1,65))))
            self.assertTrue(all(0<=r['x']<=16000 and 0<=r['y']<=16000 for r in self.runs),case)
            self.assertLessEqual(len(self.runs),1024)


if __name__=='__main__': unittest.main()
