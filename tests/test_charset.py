"""Real C legacy decoders, MIME/meta selection, and document ownership tests."""
import ctypes as C
import os
from pathlib import Path
import tempfile
import unittest
import test_core_regression as core


def setUpModule():
    core.setUpModule()
    core.LIB.ew_charset_name.argtypes = [C.c_char_p]
    core.LIB.ew_charset_parameter.argtypes = [C.c_char_p]
    core.LIB.ew_parse_text_source.argtypes = [C.c_char_p]


def tearDownModule():
    core.tearDownModule()


class Charset(unittest.TestCase):
    def setUp(self):
        self.proxy = os.environ.pop('HTTP_PROXY', None)
        self.charset = C.c_ubyte.in_dll(core.LIB, 'ew_document_charset')
        self.charset.value = 0

    def tearDown(self):
        if self.proxy is not None:
            os.environ['HTTP_PROXY'] = self.proxy

    def text(self):
        lib = core.LIB
        return b''.join(C.string_at(lib.qa_run_data(i), lib.qa_run_length(i))
                        for i in range(lib.qa_runs()) if lib.qa_run_kind(i) == 0)

    def parse(self, html):
        core.LIB.ew_parse(html, b'http://host/')
        return self.text()

    def response(self, body, media):
        return (b'HTTP/1.0 200 OK\r\nContent-Type: ' + media +
                b'\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)

    def fetch(self, response, image=False):
        server = core.OneHTTP(response)
        final, error = C.create_string_buffer(768), C.create_string_buffer(96)
        try:
            if image:
                with tempfile.TemporaryFile() as output:
                    n = core.LIB.ew_fetch_to_fd(server.url.encode(), output.fileno(),
                                               60000, final, error, 96)
            else:
                n = core.LIB.ew_fetch_document(server.url.encode(), final, error, 96, None)
        finally:
            server.close()
        return n, final.value, error.value

    def test_charset_names_and_mime_parameters(self):
        for label, enum in [(b'UTF-8', 0), (b'iso-8859-1', 1), (b'WINDOWS-1252', 2),
                            (b'ISO-8859-2', 3), (b'windows-1250', 4)]:
            self.assertEqual(core.LIB.ew_charset_name(label), enum)
            value = b'text/html; title="ignore;charset=utf-8"; CHARSET = "' + label + b'"'
            self.assertEqual(core.LIB.ew_charset_parameter(value), enum)
        self.assertEqual(core.LIB.ew_charset_parameter(b'text/html; title="charset=windows-1252"'), -1)
        self.assertEqual(core.LIB.ew_charset_parameter(b'text/html; xcharset=windows-1252'), -1)
        self.assertEqual(core.LIB.ew_charset_parameter(b'text/html; charset=x-unknown'), -1)
        self.assertEqual(core.LIB.ew_charset_name(b'x' * 200), -1)

    def test_every_high_byte_matches_unicode_decode(self):
        for label, codec in [(b'ISO-8859-1', 'latin1'), (b'Windows-1252', 'cp1252'),
                             (b'ISO-8859-2', 'iso8859_2'), (b'Windows-1250', 'cp1250')]:
            for byte in range(128, 256):
                with self.subTest(label=label, byte=byte):
                    char = bytes([byte]).decode(codec, errors='replace').encode('utf-8')
                    expected = self.parse(b'<p>x' + char + b'y</p>')
                    actual = self.parse(b'<meta charset="' + label + b'"><p>x' + bytes([byte]) + b'y</p>')
                    self.assertEqual(actual, expected)

    def test_meta_http_equiv_and_title(self):
        text = self.parse(b'<meta content="text/html; CHARSET=windows-1250" http-equiv="Content-Type">'
                          b'<title>\x8a\xe9</title><p>\x8a\xe9</p>')
        self.assertEqual(text, b'Se')
        self.assertEqual(core.LIB.qa_title(), b'Se')

    def test_unknown_meta_keeps_existing_decoder(self):
        self.assertEqual(self.parse(b'<meta charset=windows-1250><meta charset=unknown>\x8a'), b'S')
        self.assertEqual(self.parse(b'<meta charset=unknown>caf\xc3\xa9'), b'cafe')

    def test_meta_can_override_mime_without_mutating_committed_metadata(self):
        n, final, error = self.fetch(self.response(b'<meta charset=windows-1250>\x8a',
                                                  b'text/html; charset=ISO-8859-1'))
        self.assertGreater(n, 0, error)
        self.assertEqual(self.charset.value, 1)
        core.LIB.ew_parse_source(final)
        self.assertEqual(self.text(), b'S')
        self.assertEqual(self.charset.value, 1)

    def test_mime_plain_text_and_default_utf8(self):
        n, final, error = self.fetch(self.response(b'caf\xe9 \x80', b'text/plain; charset="Windows-1252"'))
        self.assertGreater(n, 0, error)
        self.assertEqual(self.charset.value, 2)
        core.LIB.ew_parse_text_source(final)
        self.assertEqual(self.text(), b'cafe EUR')
        n, final, error = self.fetch(self.response(b'caf\xc3\xa9', b'text/html'))
        self.assertGreater(n, 0, error)
        self.assertEqual(self.charset.value, 0)
        core.LIB.ew_parse_source(final)
        self.assertEqual(self.text(), b'cafe')

    def test_missing_or_unknown_mime_charset_defaults_utf8(self):
        body = b'caf\xc3\xa9'
        for header in (b'', b'Content-Type: text/html; charset=unknown\r\n'):
            self.charset.value = 4
            response = (b'HTTP/1.0 200 OK\r\n' + header +
                        b'Content-Length: 5\r\n\r\n' + body)
            n, final, error = self.fetch(response)
            self.assertGreater(n, 0, error)
            self.assertEqual(self.charset.value, 0)
            core.LIB.ew_parse_source(final)
            self.assertEqual(self.text(), b'cafe')

    def test_failed_navigation_does_not_commit_charset_or_display(self):
        n, final, error = self.fetch(self.response(b'caf\xe9', b'text/html; charset=ISO-8859-1'))
        self.assertGreater(n, 0, error)
        core.LIB.ew_parse_source(final)
        self.assertEqual(self.text(), b'cafe')
        n, final, error = self.fetch(b'HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=Windows-1250\r\nContent-Length: 8\r\n\r\nx')
        self.assertLess(n, 0)
        self.assertEqual(self.charset.value, 1)
        self.assertEqual(self.text(), b'cafe')

    def test_image_fetch_does_not_commit_charset_or_source(self):
        n, final, error = self.fetch(self.response(b'caf\xe9', b'text/html; charset=ISO-8859-1'))
        self.assertGreater(n, 0, error)
        old_url = final
        n, final, error = self.fetch(self.response(b'GIF89a', b'image/gif; charset=Windows-1250'), image=True)
        self.assertGreater(n, 0, error)
        self.assertEqual(self.charset.value, 1)
        core.LIB.ew_parse_source(old_url)
        self.assertEqual(self.text(), b'cafe')

    def test_local_document_and_direct_parse_default_utf8(self):
        self.charset.value = 4
        self.assertEqual(self.parse(b'caf\xc3\xa9'), b'cafe')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'utf8.htm'
            path.write_bytes(b'caf\xc3\xa9')
            final, error = C.create_string_buffer(768), C.create_string_buffer(96)
            self.assertGreater(core.LIB.ew_fetch_document(str(path).encode(), final, error, 96, None), 0)
            self.assertEqual(self.charset.value, 0)
            core.LIB.ew_parse_source(final.value)
            self.assertEqual(self.text(), b'cafe')

    def test_entities_are_unicode_and_url_form_bytes_are_preserved(self):
        result = self.parse(b'<meta charset=windows-1250><p>&#233; &#x160;</p>'
                            b'<a href="/caf\xe9">link</a>'
                            b'<form action=/send><input name=q value="caf\xe9"><input type=submit value=Go></form>')
        self.assertIn(b'e S', result)
        self.assertEqual(core.LIB.qa_link(0), b'http://host/caf\xe9')
        # Controls use canonical UTF-8 internally; serialization retains the source charset.
        self.assertEqual(core.LIB.qa_link_value(1), b'caf\xc3\xa9')
        url, post = C.create_string_buffer(768), C.create_string_buffer(768)
        self.assertEqual(core.LIB.ew_form_url(2, url, 768, post, 768), 0)
        self.assertIn(b'q=caf%E9', url.value)

    def test_legacy_alt_and_entity_normalization_are_display_only(self):
        self.parse(b'<meta charset=windows-1250><img src="/caf\xe9.gif" alt="caf\xe9 &#233; \x8a">')
        pointer = core.LIB.qa_run_data(0)
        url = C.string_at(pointer)
        self.assertEqual(url, b'http://host/caf\xe9.gif')
        self.assertEqual(C.string_at(pointer + len(url) + 1), b'cafe e S')

    def test_redirect_charset_is_final_response_only(self):
        first = (b'HTTP/1.0 302 Found\r\nLocation: /final\r\n'
                 b'Content-Type: text/html; charset=Windows-1250\r\nContent-Length: 0\r\n\r\n')
        n, final, error = self.fetch([first, self.response(b'caf\xc3\xa9', b'text/html')])
        self.assertGreater(n, 0, error)
        self.assertEqual(self.charset.value, 0)
        core.LIB.ew_parse_source(final)
        self.assertEqual(self.text(), b'cafe')


if __name__ == '__main__':
    unittest.main()
