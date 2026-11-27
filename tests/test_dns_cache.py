"""Resolver reuse is bounded by document loads, with one stale-address retry."""
import ctypes as C
import pathlib
import subprocess
import tempfile
import unittest
from test_core_regression import OneHTTP

ROOT = pathlib.Path(__file__).resolve().parents[1]

class DNSCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-dns-qa-')
        library = pathlib.Path(cls.temp.name) / 'dns.dylib'
        sources = ['src/url.c', 'src/html.c', 'src/memory.c', 'font/font.c',
                   'font/body_font.c', 'tests/qa_core_shim.c', 'tests/qa_dns_net.c']
        subprocess.run(['cc', '-shared', '-fPIC', '-g', '-DEW_HOST_TEST',
                        '-I'+str(ROOT/'src'), '-I'+str(ROOT/'font'),
                        *[str(ROOT/s) for s in sources], '-o', str(library)],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(library))
        cls.lib.ew_fetch_document.argtypes = [C.c_char_p, C.c_void_p, C.c_void_p, C.c_uint, C.c_char_p]
        cls.lib.ew_fetch.argtypes = [C.c_char_p, C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p, C.c_uint, C.c_char_p]
        cls.lib.ew_fetch_document.restype = cls.lib.ew_fetch.restype = C.c_int32

    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_source_free()
        cls.temp.cleanup()

    def fetch(self, url, document=False):
        final, error = C.create_string_buffer(1024), C.create_string_buffer(128)
        if document:
            result = self.lib.ew_fetch_document(url.encode(), final, error, 128, None)
        else:
            result = self.lib.ew_fetch(url.encode(), C.create_string_buffer(64), 64, final, error, 128, None)
        return result, error.value

    def test_reuse_within_page_but_resolve_again_on_reload(self):
        server = OneHTTP([b'HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nx']*4)
        url = server.url.replace('127.0.0.1', 'images.test')
        initial = self.lib.qa_dns_lookups()
        try:
            self.assertEqual(self.fetch(url, True), (1, b''))
            self.assertEqual(self.fetch(url+'/one.gif'), (1, b''))
            self.assertEqual(self.fetch(url+'/two.gif'), (1, b''))
            self.assertEqual(self.lib.qa_dns_lookups()-initial, 1)
            self.assertEqual(self.fetch(url, True), (1, b''))
            self.assertEqual(self.lib.qa_dns_lookups()-initial, 2)
        finally: server.close()

    def test_cached_connection_failure_resolves_again_once(self):
        server = OneHTTP([b'HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nx']*2)
        url = server.url.replace('127.0.0.1', 'images.test')
        try:
            self.assertEqual(self.fetch(url, True), (1, b''))
            initial = self.lib.qa_dns_lookups()
            self.lib.qa_dns_fail_connections(1)
            self.assertEqual(self.fetch(url+'/image.gif'), (1, b''))
            self.assertEqual(self.lib.qa_dns_lookups()-initial, 1)
        finally: server.close()

    def test_repeated_connection_failure_stops_after_one_retry(self):
        server = OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nx')
        url = server.url.replace('127.0.0.1', 'images.test')
        try:
            self.assertEqual(self.fetch(url, True), (1, b''))
            initial = self.lib.qa_dns_lookups()
            self.lib.qa_dns_fail_connections(2)
            self.assertEqual(self.fetch(url+'/image.gif'), (-1, b'Connection failed'))
            self.assertEqual(self.lib.qa_dns_lookups()-initial, 1)
        finally: server.close()

if __name__ == '__main__': unittest.main()
