"""Whitespace and literal-text behavior of the real C parser and shared font."""
import ctypes as C
import pathlib
import tempfile
import unittest
import test_core_regression as core


def setUpModule():
    core.setUpModule()
    core.LIB.ew_parse_text_source.argtypes = [C.c_char_p]


def tearDownModule():
    core.tearDownModule()


class Monospace(unittest.TestCase):
    def runs(self):
        lib = core.LIB
        return [(C.string_at(lib.qa_run_data(i), lib.qa_run_length(i)),
                 lib.qa_x(i), lib.qa_y(i), lib.qa_style(i))
                for i in range(lib.qa_runs()) if lib.qa_run_kind(i) == 0]

    def parse(self, html):
        core.LIB.ew_parse(html, b'http://host/')
        return self.runs()

    def test_fixed_cell_metrics(self):
        lib = core.LIB
        for size, width, height in [(0, 8, 6), (1, 9, 8), (2, 12, 10)]:
            for bold in (0, 1):
                self.assertEqual({lib.ew_mono_char_width(c, bold, size)
                                  for c in range(32, 127)}, {width + bold})
                self.assertEqual(lib.ew_mono_width(b'Wi.!', 4, bold, size),
                                 4 * (width + bold))
            self.assertEqual(lib.ew_mono_height(size), height)

    def test_aliases_and_nested_style_restore(self):
        runs = self.parse(b'<code>A<tt>B</tt>C</code>D<samp>E</samp><kbd>F</kbd>G')
        self.assertEqual(b''.join(t for t, x, y, s in runs if s & 64), b'ABCEF')
        self.assertEqual(b''.join(t for t, x, y, s in runs if not s & 64), b'DG')

    def test_pre_exact_spaces_no_extra_gap(self):
        runs = self.parse(b'<pre> A  B C</pre>')
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][0], b' A  B C')
        self.assertEqual(runs[0][1], 0)
        self.assertEqual(core.LIB.ew_mono_width(runs[0][0], len(runs[0][0]), 0, 1), 63)

    def test_pre_tab_stops_and_crlf(self):
        runs = self.parse(b'<pre>A\tB\r\n  C\tD</pre>')
        self.assertEqual([r[0] for r in runs], [b'A       B', b'  C     D'])
        self.assertEqual(runs[1][2] - runs[0][2], 8)

    def test_pre_empty_lines(self):
        runs = self.parse(b'<pre>A\n\n\nB</pre>')
        self.assertEqual(runs[1][2] - runs[0][2], 24)

    def test_pre_entity_decoding_still_html(self):
        runs = self.parse(b'<pre>&lt;b&gt;&amp;</pre>')
        self.assertEqual(b''.join(r[0] for r in runs), b'<b>&')

    def test_nested_pre_mono_state(self):
        runs = self.parse(b'<code>A<pre>B</pre>C</code>D')
        self.assertEqual(b''.join(t for t, x, y, s in runs if s & 64), b'ABC')
        self.assertEqual(b''.join(t for t, x, y, s in runs if not s & 64), b'D')

    def test_plain_text_literal_and_html_mode_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'literal.txt'
            path.write_bytes(b'<b>A</b> &amp;\n\nX\tY\r\n')
            final, error = C.create_string_buffer(768), C.create_string_buffer(96)
            n = core.LIB.ew_fetch_document(str(path).encode(), final, error, 96, None)
            self.assertGreater(n, 0, error.value)
            core.LIB.ew_parse_text_source(final.value)
            runs = self.runs()
            self.assertEqual([r[0] for r in runs], [b'<b>A</b> &amp;', b'X       Y'])
            self.assertTrue(all(r[3] & 64 and r[3] & 32 for r in runs))
            self.assertEqual(runs[1][2] - runs[0][2], 12)
            runs = self.parse(b'<b>normal</b>')
            self.assertEqual(runs[0][0], b'normal')
            self.assertFalse(runs[0][3] & 64)

    def test_tabs_after_inline_markup_use_logical_column(self):
        runs = self.parse(b'<pre>A<b>B</b>\tC</pre>')
        self.assertEqual(b''.join(r[0] for r in runs), b'AB      C')


if __name__ == '__main__':
    unittest.main()
