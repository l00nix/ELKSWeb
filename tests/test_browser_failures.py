"""Fault-inject actual main/navigation/save/core/image code; no native ABI claim."""
import ctypes as C
import os
import pathlib
import socket
import subprocess
import tempfile
import unittest
from test_core_regression import OneHTTP

ROOT=pathlib.Path(__file__).resolve().parents[1]

class BrowserFailures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='ew-recovery-')
        folder=pathlib.Path(cls.tmp.name)
        sources=[ROOT/'src'/(s+'.c') for s in ('html','url','net','images')]
        sources += [ROOT/'font/font.c',ROOT/'font/body_font.c',ROOT/'image/dimensions.c',
                    ROOT/'tests/qa_browser_failure_shim.c',ROOT/'tests/qa_fault_memory.c',
                    ROOT/'tests/qa_fault_gif.c']
        cls.library=folder/'browser.so'
        subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-DEW_QA_REAL_IMAGES',
                        '-I'+str(ROOT/'src'),'-I'+str(ROOT/'platform'),
                        *map(str,sources),'-o',str(cls.library)],check=True,capture_output=True)
        cls.lib=C.CDLL(str(cls.library))
        cls.lib.qa_browser_load.argtypes=[C.c_char_p]
        cls.lib.qa_browser_save.argtypes=[C.c_char_p,C.c_uint,C.c_int]
        for name in ('qa_browser_status','qa_browser_current','qa_title','qa_link'):
            getattr(cls.lib,name).restype=C.c_char_p
        cls.lib.ew_image_lookup.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p]
        cls.home=folder/'home.htm'
        cls.home.write_bytes(b'<title>Safe home</title><p>Retained page</p><a href="next.htm">Next</a>')
        cls.next=folder/'next.htm';cls.next.write_bytes(b'<title>Next page</title><p>Recovered</p>')
        cls.payload=bytes(range(256))*7+b'END\0'

    @classmethod
    def tearDownClass(cls):
        cls.lib.qa_browser_reset();cls.tmp.cleanup()

    def setUp(self):
        self.old_proxy=os.environ.pop('HTTP_PROXY',None)
        self.lib.qa_browser_reset();self.lib.qa_allocator_reset(0);self.lib.qa_io_reset(0)
        self.assertEqual(self.lib.qa_allocator_live(),0)
        self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.home)),1)

    def tearDown(self):
        self.lib.qa_allocator_reset(0);self.lib.qa_io_reset(0)
        self.lib.qa_browser_reset();self.assertEqual(self.lib.qa_allocator_live(),0)
        if self.old_proxy is not None:os.environ['HTTP_PROXY']=self.old_proxy

    def intact(self):
        self.assertEqual(self.lib.qa_title(),b'Safe home')
        self.assertEqual(self.lib.qa_browser_current(),os.fsencode(self.home))
        self.assertEqual(self.lib.qa_links(),1)
        self.assertTrue(self.lib.qa_link(0).endswith(b'/next.htm'))
        self.assertEqual(self.lib.qa_browser_history_count(),1)
        self.assertTrue(self.lib.qa_browser_status())

    def recover(self):
        self.lib.qa_allocator_reset(0);self.lib.qa_io_reset(0)
        self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.next)),1)
        self.assertEqual(self.lib.qa_title(),b'Next page')
        self.lib.qa_browser_back();self.assertEqual(self.lib.qa_title(),b'Safe home')

    def binary(self):
        response=b'HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: '+str(len(self.payload)).encode()+b'\r\n\r\n'+self.payload
        server=OneHTTP(response)
        try:self.assertEqual(self.lib.qa_browser_load(server.url.encode()+b'/download.bin'),0)
        finally:server.close()
        self.assertTrue(self.lib.qa_browser_download_open())

    def test_failed_navigation_preserves_old_page_and_history(self):
        responses=(b'not an HTTP response\r\n\r\n',
                   b'HTTP/1.0 200 OK\r\nContent-Length: 99\r\n\r\nshort',
                   b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhi')
        for response in responses:
            server=OneHTTP(response)
            try:self.assertEqual(self.lib.qa_browser_load(server.url.encode()+b'/bad'),0)
            finally:server.close()
            self.intact()
        self.recover()

    def test_refused_connection_preserves_page_then_recovers(self):
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0))
            url=f'http://127.0.0.1:{reserved.getsockname()[1]}/'.encode()
            self.assertEqual(self.lib.qa_browser_load(url),0)
        self.intact();self.recover()

    def test_cache_create_write_flush_rewind_failure_preserves_page(self):
        for fault in (1,2,4,16,32):
            self.lib.qa_io_reset(fault)
            self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.next)),0)
            self.intact()
        self.recover()

    def test_save_partial_write_close_zero_write_and_cancel_cleanup(self):
        self.binary()
        with tempfile.TemporaryDirectory(prefix='ew-save-') as folder:
            path=pathlib.Path(folder)/'out.bin'
            for fault,cancel in ((2,0),(4,0),(64,0),(0,1)):
                self.lib.qa_browser_save(os.fsencode(path),fault,cancel)
                self.assertFalse(path.exists(),(fault,cancel))
                self.assertIn(b'incomplete file removed',self.lib.qa_browser_status())
                self.assertTrue(self.lib.qa_browser_download_open())
            self.lib.qa_browser_save(os.fsencode(path),16|32,0)
            self.assertEqual(path.read_bytes(),self.payload)
            self.assertFalse(self.lib.qa_browser_download_open())
        self.recover()

    def test_save_create_failure_and_existing_file_leave_bytes_untouched(self):
        self.binary()
        with tempfile.TemporaryDirectory(prefix='ew-save-') as folder:
            path=pathlib.Path(folder)/'out.bin'
            self.lib.qa_browser_save(os.fsencode(path),1,0)
            self.assertFalse(path.exists());self.assertIn(b'Cannot create',self.lib.qa_browser_status())
            path.write_bytes(b'Keep existing bytes')
            self.lib.qa_browser_save(os.fsencode(path),0,0)
            self.assertEqual(path.read_bytes(),b'Keep existing bytes')
            self.assertIn(b'File exists',self.lib.qa_browser_status())
        self.lib.qa_browser_cancel_download();self.recover()

    def test_cleanup_failure_reports_remaining_partial_file(self):
        self.binary()
        with tempfile.TemporaryDirectory(prefix='ew-save-') as folder:
            path=pathlib.Path(folder)/'out.bin'
            self.lib.qa_browser_save(os.fsencode(path),2|8,0)
            self.assertEqual(path.read_bytes(),self.payload[:23])
            self.assertIn(b'incomplete file remains',self.lib.qa_browser_status())
            self.assertNotIn(b'removed',self.lib.qa_browser_status())
        self.lib.qa_browser_cancel_download();self.recover()

    def test_save_cache_read_failure_removes_file_and_recovers(self):
        self.binary();self.lib.qa_io_reset(8)
        with tempfile.TemporaryDirectory(prefix='ew-save-') as folder:
            path=pathlib.Path(folder)/'out.bin'
            self.lib.qa_browser_save(os.fsencode(path),0,0)
            self.assertFalse(path.exists())
        self.lib.qa_browser_cancel_download();self.recover()

    def test_first_document_allocation_failure_allows_retry(self):
        for fault in (1,2):
            self.lib.qa_browser_reset();self.lib.qa_allocator_reset(fault)
            self.lib.qa_browser_load(os.fsencode(self.home))
            self.assertEqual(self.lib.qa_runs(),0)
            self.assertIn(b'memory',self.lib.qa_title().lower())
            self.lib.qa_allocator_reset(0)
            self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.home)),1)
            self.assertEqual(self.lib.qa_title(),b'Safe home')
            self.assertEqual(self.lib.qa_links(),1)

    def test_malformed_and_truncated_image_documents_allow_navigation(self):
        gif=(ROOT/'tests/fixtures/frogfind/frog.gif').read_bytes()
        with tempfile.TemporaryDirectory(prefix='ew-image-fail-') as folder:
            path=pathlib.Path(folder)/'bad.gif'
            for body in (b'',b'not a GIF',gif[:20]):
                path.write_bytes(body)
                self.assertEqual(self.lib.qa_browser_load(os.fsencode(path)),1)
                self.assertTrue(self.lib.qa_browser_status())
                self.assertLess(self.lib.ew_image_lookup(os.fsencode(path),None,None),0)
                self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.next)),1)
                self.assertEqual(self.lib.qa_title(),b'Next page')

    def test_image_allocation_failures_are_explicit_and_recoverable(self):
        gif=ROOT/'tests/fixtures/frogfind/frog.gif'
        for fault in range(1,6):
            self.lib.qa_allocator_reset(fault)
            self.assertEqual(self.lib.qa_browser_load(os.fsencode(gif)),1)
            self.assertIn(b'memory',self.lib.qa_browser_status(),fault)
            self.lib.qa_allocator_reset(0)
            self.assertEqual(self.lib.qa_browser_load(os.fsencode(gif)),1)
            self.assertGreaterEqual(self.lib.ew_image_lookup(os.fsencode(gif),None,None),0)
        self.assertEqual(self.lib.qa_browser_load(os.fsencode(self.next)),1)
        self.assertEqual(self.lib.qa_title(),b'Next page')

if __name__=='__main__':unittest.main()
