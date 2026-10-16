"""Failure injection into actual storage implementation; no native-memory claim."""
import ctypes as C
import pathlib
import subprocess
import tempfile
import unittest

HERE=pathlib.Path(__file__).resolve().parent
SRC=HERE.parent/'src'

class AllocationFailures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='elksweb-allocation-qa-')
        library=pathlib.Path(cls.temp.name)/'core.dylib'
        subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-I'+str(SRC),'-I'+str(HERE.parent/'font'),str(SRC/'url.c'),str(SRC/'html.c'),str(SRC/'net.c'),str(HERE.parent/'font/font.c'),str(HERE.parent/'font/body_font.c'),str(HERE/'qa_core_shim.c'),str(HERE/'qa_fault_memory.c'),'-o',str(library)],check=True,capture_output=True)
        cls.lib=C.CDLL(str(library))
        cls.lib.ew_parse.argtypes=[C.c_char_p,C.c_char_p]
        cls.lib.ew_source_put.argtypes=[C.c_uint32,C.c_ubyte]
        cls.lib.ew_fetch_document.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p]
        cls.lib.ew_fetch_document.restype=C.c_int32
        cls.lib.qa_title.restype=C.c_char_p
        cls.lib.ew_source_error.restype=C.c_char_p
        cls.lib.ew_parse_source.argtypes=[C.c_char_p]
        cls.lib.ew_source_byte.argtypes=[C.c_uint32]
        cls.lib.ew_source_byte.restype=C.c_ubyte
    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_source_free();cls.temp.cleanup()
    def setUp(self):
        self.lib.ew_source_free();self.lib.qa_allocator_reset(0);self.lib.qa_io_reset(0)
        self.assertEqual(self.lib.qa_allocator_live(),0)
    def tearDown(self):
        self.lib.ew_source_free();self.assertEqual(self.lib.qa_allocator_live(),0)
    def test_first_source_allocation_failure_then_retry(self):
        self.lib.qa_allocator_reset(1)
        self.assertEqual(self.lib.ew_source_init(),-1)
        self.lib.qa_allocator_reset(0)
        self.assertEqual(self.lib.ew_source_init(),0)
    def test_second_source_failure_is_explicit_then_retry(self):
        self.lib.qa_allocator_reset(2)
        self.assertEqual(self.lib.ew_source_init(),0)
        self.assertEqual(self.lib.ew_source_put(60000,65),-1)
        self.lib.qa_allocator_reset(0)
        self.assertEqual(self.lib.ew_source_put(60000,65),0)
    def test_spooled_fetch_avoids_far_source_allocation(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'x'*90000);file.flush()
            self.lib.qa_allocator_reset(2)
            final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            result=self.lib.ew_fetch_document(file.name.encode(),final,error,128,None)
        self.assertEqual(result,90000)
        self.assertEqual(self.lib.qa_allocator_live(),0)
    def test_document_allocation_failure_is_bounded_and_recoverable(self):
        for fail_at in (1,2):
            with self.subTest(fail_at=fail_at):
                self.lib.ew_source_free();self.lib.qa_allocator_reset(fail_at)
                self.lib.ew_parse(b'<p>Readable text</p>',b'http://host/')
                self.assertEqual(self.lib.qa_runs(),0)
                self.assertIn(b'memory',self.lib.qa_title().lower())
                self.lib.qa_allocator_reset(0)
                self.lib.ew_parse(b'<p>Readable text</p>',b'http://host/')
                self.assertGreater(self.lib.qa_runs(),0)
    def test_url_pool_failure_preserves_readable_text(self):
        self.lib.qa_allocator_reset(3)
        self.lib.ew_parse(b'<a href="/article">Headline</a><p>Following text</p>',b'http://host/')
        self.assertGreater(self.lib.qa_text_len(),len('Headline'))
        self.assertTrue(self.lib.qa_truncated())

    def test_cache_create_write_flush_seek_failure_reports_error(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'<p>Cache test</p>');file.flush()
            for failure in (1,2,4,16):
                with self.subTest(failure=failure):
                    self.lib.qa_io_reset(failure)
                    final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
                    result=self.lib.ew_fetch_document(file.name.encode(),final,error,128,None)
                    self.assertLess(result,0);self.assertTrue(error.value)
                    self.assertEqual(C.c_uint32.in_dll(self.lib,'ew_source_length').value,0)
                    self.lib.qa_io_reset(0)
    def test_cache_read_failure_is_visible_and_document_flagged(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'<p>Cache test</p>');file.flush()
            final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            self.assertGreater(self.lib.ew_fetch_document(file.name.encode(),final,error,128,None),0)
            self.lib.qa_io_reset(8);self.lib.ew_parse_source(b'http://host/')
            self.assertTrue(self.lib.ew_source_error());self.assertTrue(self.lib.qa_truncated())
            self.lib.qa_io_reset(0)

    def test_cache_seek_failure_never_exposes_stale_cached_bytes(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'A'*512+b'B'*1536);file.flush()
            final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            self.assertEqual(self.lib.ew_fetch_document(file.name.encode(),final,error,128,None),2048)
            self.assertEqual(self.lib.ew_source_byte(0),ord('A'))
            self.lib.qa_io_reset(4)
            for offset in (1024,1025,1030,0):self.assertEqual(self.lib.ew_source_byte(offset),0)
            self.lib.qa_io_reset(0)
            self.assertEqual(self.lib.ew_source_byte(1025),0)
            self.assertEqual(self.lib.ew_fetch_document(file.name.encode(),final,error,128,None),2048)
            self.assertEqual(self.lib.ew_source_byte(1025),ord('B'))

if __name__=='__main__':unittest.main()
