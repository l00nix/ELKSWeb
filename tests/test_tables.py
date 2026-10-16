"""Bounded native table layout: compile production parser and inspect its runs."""
import ctypes as C
import pathlib
import random
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent

class Tables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-tables-')
        path = pathlib.Path(cls.temp.name)
        extra = path / 'extra.c'
        extra.write_text('#include "elksweb.h"\nunsigned table_height(unsigned i){return ew_doc.runs[i].off ? ew_doc.runs[i].off : ew_doc.runs[i].w;}\nunsigned table_context_bytes(void);\n')
        src = HERE.parent / 'src'
        sources = [src / (name + '.c') for name in ('html', 'url', 'net', 'memory')]
        sources += [HERE.parent/'font/font.c', HERE.parent/'font/body_font.c', HERE/'qa_core_shim.c', extra]
        library = path / 'tables.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-g', '-DEW_HOST_TEST', '-I'+str(src),
                        '-I'+str(HERE.parent/'font'), *map(str, sources), '-o', str(library)],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(library))
        cls.lib.ew_parse.argtypes = [C.c_char_p, C.c_char_p]
        cls.lib.qa_run_data.restype = C.c_void_p
        cls.lib.ew_body_width.argtypes = [C.c_char_p, C.c_uint, C.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_source_free()
        cls.temp.cleanup()

    def parse(self, html):
        self.lib.ew_parse(html.encode(), b'http://host/table.htm')
        self.runs = []
        for i in range(self.lib.qa_runs()):
            kind = self.lib.qa_run_kind(i)
            text = C.string_at(self.lib.qa_run_data(i), self.lib.qa_run_length(i)) if kind == 0 else b''
            self.runs.append(dict(i=i, kind=kind, text=text, x=self.lib.qa_x(i), y=self.lib.qa_y(i),
                                  width=self.lib.qa_run_length(i), height=self.lib.table_height(i),
                                  style=self.lib.qa_style(i)))
        return self.runs

    def texts(self):
        return [r for r in self.runs if r['kind'] == 0]

    def boxes(self):
        return [r for r in self.runs if r['kind'] == 6]

    def test_defaults_use_two_pixel_padding_and_spacing(self):
        self.parse('<table border=1><tr><td>A</td><td>B</td></tr></table>')
        a, b = self.texts()
        aw = self.lib.ew_body_width(b'A', 1, 0)
        self.assertEqual((a['x'], a['y']), (4, 4))
        self.assertEqual(b['x'], 4 + aw + 4 + 2)
        self.assertEqual(len(self.boxes()), 3)
        self.assertEqual(self.boxes()[-1]['height'], 16)
        self.assertFalse(self.lib.qa_truncated())

    def test_zero_padding_spacing_are_honored(self):
        self.parse('<table border=1 cellpadding=0 cellspacing=0><tr><td>A</td><td>B</td></tr></table>')
        a, b = self.texts()
        self.assertEqual((a['x'], a['y']), (0, 0))
        self.assertEqual(b['x'], self.lib.ew_body_width(b'A', 1, 0))
        self.assertEqual(self.boxes()[-1]['height'], 8)

    def test_explicit_table_width_is_distributed(self):
        self.parse('<table border=1 width=300><tr><td>A</td><td>B</td></tr></table>')
        self.assertEqual(self.boxes()[-1]['width'], 300)
        self.assertGreater(self.texts()[1]['x'], 140)

    def test_percent_table_and_cell_widths(self):
        self.parse('<table border=1 width="50%"><tr><td width="75%">A</td><td>B</td></tr></table>')
        self.assertEqual(self.boxes()[-1]['width'], 312)
        self.assertGreaterEqual(self.boxes()[0]['width'], 234)

    def test_explicit_cell_width(self):
        self.parse('<table border=1><tr><td width=100>A</td><td>B</td></tr></table>')
        self.assertEqual(self.boxes()[0]['width'], 100)
        self.assertEqual(self.texts()[1]['x'], 106)

    def test_colspan_preserves_following_column(self):
        self.parse('<table border=1><tr><td colspan=2>Wide heading</td><td>C</td></tr><tr><td>A</td><td>B</td><td>D</td></tr></table>')
        texts = {r['text']: r for r in self.texts()}
        self.assertEqual(texts[b'C']['x'], texts[b'D']['x'])
        self.assertGreater(texts[b'B']['x'], texts[b'A']['x'])
        self.assertEqual(texts[b'A']['y'], texts[b'B']['y'])
        cells = self.boxes()
        self.assertEqual(cells[0]['width'], cells[2]['width'] + cells[3]['width'] + 2)

    def test_omitted_row_and_cell_closing_tags(self):
        self.parse('<table><tr><td>A<td>B<tr><td>C<td>D</table>')
        a, b, c, d = self.texts()
        self.assertEqual(a['x'], c['x'])
        self.assertEqual(b['x'], d['x'])
        self.assertGreater(c['y'], a['y'])

    def test_two_nested_tables_and_following_content(self):
        self.parse('<table border=1><tr><td>Before<table border=1><tr><td>Inner</td></tr></table>After</td><td>Peer</td></tr></table>End')
        texts = {r['text']: r for r in self.texts()}
        self.assertGreater(texts[b'Inner']['y'], texts[b'Before']['y'])
        self.assertGreater(texts[b'After']['y'], texts[b'Inner']['y'])
        self.assertGreater(texts[b'Peer']['x'], texts[b'Inner']['x'])
        self.assertGreater(texts[b'End']['y'], texts[b'After']['y'])
        self.assertFalse(self.lib.qa_truncated())

    def test_unclosed_nested_tables_finalize_at_eof(self):
        self.parse('<table border=1><tr><td>A<table border=1><tr><td>B')
        self.assertEqual(len(self.boxes()), 4)
        self.assertGreater(self.texts()[1]['y'], self.texts()[0]['y'])

    def test_tall_border_preserves_full_height(self):
        self.parse('<table border=1><tr><td>' + '<p>A</p>' * 60 + '</td></tr></table>')
        self.assertGreater(self.boxes()[-1]['height'], 255)
        self.assertGreater(self.boxes()[0]['height'], 255)

    def test_wide_table_not_clamped_to_viewport(self):
        self.parse('<table border=1 width=1400><tr><td>A</td><td>B</td></tr></table>')
        self.assertEqual(self.boxes()[-1]['width'], 1400)
        self.assertGreater(self.texts()[1]['x'], 624)
        self.assertFalse(self.lib.qa_truncated())

    def test_header_style_does_not_leak(self):
        self.parse('<table><tr><th>A</th><td>B</td></tr></table>C')
        a, b, c = self.texts()
        self.assertTrue(a['style'] & 1)
        self.assertFalse((b['style'] | c['style']) & 1)

    def test_malformed_negative_coordinate_regression(self):
        for html in ('<table>#<td><li>', '<table>text<td><li>item</li></td></table>',
                     '<table>AAAA<td><br>X</td></table>'):
            self.parse(html)
            self.assertTrue(all(r['x'] >= 0 and r['y'] >= 0 for r in self.runs), html)

    def test_bounded_random_table_geometry(self):
        rng = random.Random(4042)
        tags = ['<table border=1>', '<table width=999999 cellpadding=999 cellspacing=999>',
                '</table>', '<tr>', '</tr>', '<td>', '<td colspan=8 width="100%">',
                '<td colspan=-1>', '</td>', '<th>', '</th>', '<br>', '<p>', '</p>',
                '<ul><li>', '</ul>', 'word ', 'x' * 120]
        for case in range(400):
            self.parse(''.join(rng.choice(tags) for _ in range(rng.randrange(1, 65))))
            self.assertTrue(all(0 <= r['x'] <= 16000 and 0 <= r['y'] <= 16000 for r in self.runs), case)
            self.assertLessEqual(len(self.runs), 1024)

if __name__ == '__main__':
    unittest.main()
