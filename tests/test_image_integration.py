"""Actual HTML/source/HTTP/GIF/cache integration, rendered pixels tested separately."""
import ctypes as C, pathlib, subprocess, tempfile, unittest
from test_core_regression import OneHTTP
HERE=pathlib.Path(__file__).resolve().parent
SRC=HERE.parent/'src'
class Images(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='elksweb-image-qa-');library=pathlib.Path(cls.temp.name)/'core.dylib'
        sources=[SRC/(s+'.c') for s in ('html','url','net','images')]+[HERE.parent/'font/font.c',HERE.parent/'font/body_font.c',HERE.parent/'image/gif.c',HERE.parent/'image/dimensions.c',HERE/'qa_image_shim.c',HERE/'qa_fault_memory.c']
        subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-DEW_QA_REAL_IMAGES','-I'+str(SRC),'-I'+str(HERE.parent/'font'),'-I'+str(HERE.parent/'platform'),*[str(s) for s in sources],'-o',str(library)],check=True,capture_output=True)
        cls.lib=C.CDLL(str(library));cls.lib.ew_fetch_document.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p];cls.lib.ew_fetch_document.restype=C.c_int32
        cls.lib.ew_parse_source.argtypes=[C.c_char_p];cls.lib.ew_parse.argtypes=[C.c_char_p,C.c_char_p];cls.lib.ew_source_byte.argtypes=[C.c_uint32];cls.lib.ew_source_byte.restype=C.c_ubyte
        cls.lib.ew_images_load_document.argtypes=[C.c_char_p];cls.lib.ew_image_document_error.restype=C.c_char_p
        cls.lib.ew_image_lookup.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p]
    @classmethod
    def tearDownClass(cls):cls.lib.ew_images_clear();cls.lib.ew_source_free();cls.temp.cleanup()
    def setUp(self):self.lib.ew_images_clear();self.lib.ew_source_free();self.lib.qa_io_reset(0);self.lib.qa_allocator_reset(0)
    def test_gif_load_preserves_entire_spooled_html_for_reflow(self):
        image=(HERE/'fixtures/image.gif').resolve();html=b'<!--'+b'x'*90000+b'--><p>Before</p><img src="'+str(image).encode()+b'"><p>After</p>'
        with tempfile.NamedTemporaryFile() as source:
            source.write(html);source.flush();final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            self.assertEqual(self.lib.ew_fetch_document(source.name.encode(),final,error,128,None),len(html))
            self.lib.ew_parse_source(source.name.encode());self.lib.ew_images_load()
            width=C.c_uint();height=C.c_uint()
            self.assertGreaterEqual(self.lib.ew_image_lookup(str(image).encode(),C.byref(width),C.byref(height)),0)
            self.assertEqual((width.value,height.value),(16,16))
            self.assertEqual(bytes(self.lib.ew_source_byte(i) for i in range(len(html))),html)
            self.lib.ew_parse_source(source.name.encode());self.assertFalse(self.lib.qa_truncated());self.assertGreater(self.lib.qa_text_len(),0)
    def test_duplicate_successful_images_fetch_once(self):
        gif=(HERE/'fixtures/image.gif').read_bytes();server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: '+str(len(gif)).encode()+b'\r\n\r\n'+gif)
        try:
            url=(server.url+'/image.gif').encode();self.lib.ew_parse((b'<img src="'+url+b'">')*3,b'http://host/')
            self.lib.ew_images_load();self.lib.ew_images_load()
            self.assertGreaterEqual(self.lib.ew_image_lookup(url,None,None),0)
        finally:server.close()
        self.assertEqual(len(server.requests),1)
    def test_failed_image_cached_until_page_clear(self):
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: 3\r\n\r\nbad')
        try:
            url=(server.url+'/bad.gif').encode();self.lib.ew_parse((b'<img src="'+url+b'">')*3,b'http://host/')
            self.lib.ew_images_load();self.lib.ew_images_load()
            self.assertLess(self.lib.ew_image_lookup(url,None,None),0)
        finally:server.close()
        self.assertEqual(len(server.requests),1)

    def direct_document(self, body, extension, expected, dimensions):
        response=b'HTTP/1.0 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nContent-Type: image/'+extension.encode()+b'\r\n\r\n'+body
        server=OneHTTP(response)
        try:
            url=(server.url+'/direct.'+extension).encode();final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            self.assertEqual(self.lib.ew_fetch_document(url,final,error,128,None),len(body))
            self.assertEqual(self.lib.ew_images_load_document(url),expected)
            width=C.c_uint();height=C.c_uint();index=self.lib.ew_image_lookup(url,C.byref(width),C.byref(height))
            self.assertEqual((width.value,height.value),dimensions)
            self.assertEqual(index>=0,expected==0)
            self.assertEqual(bytes(self.lib.ew_source_byte(i) for i in range(len(body))),body)
            self.assertEqual(bool(self.lib.ew_image_document_error()),expected!=0)
        finally:server.close()
        self.assertEqual(len(server.requests),1,'Direct images must reuse document bytes, not refetch')
    def test_direct_gif_one_request_preserves_source(self):
        self.direct_document((HERE/'fixtures/image.gif').read_bytes(),'gif',0,(16,16))
    def test_direct_png_metadata_is_explicitly_unsupported(self):
        import struct,zlib
        def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',200,150,8,0,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff'*200)*150))+chunk(b'IEND',b'')
        self.direct_document(png,'png',1,(200,150))
    def test_direct_gif_over_decoder_capacity_retains_metadata(self):
        self.direct_document((HERE/'fixtures/image.gif').read_bytes()+b'\0'*61000,'gif',1,(16,16))
    def test_direct_invalid_image_is_explicit_failure(self):
        self.direct_document(b'not an image\0','gif',-1,(0,0))
    def test_direct_image_source_read_error_stays_failed_until_refetch(self):
        body=(HERE/'fixtures/image.gif').read_bytes()
        with tempfile.NamedTemporaryFile(suffix='.gif') as file:
            file.write(body);file.flush();url=file.name.encode();final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
            self.assertEqual(self.lib.ew_fetch_document(url,final,error,128,None),len(body))
            self.lib.qa_io_reset(8)
            self.assertEqual(self.lib.ew_images_load_document(url),-1)
            self.assertTrue(self.lib.ew_image_document_error())
            self.lib.qa_io_reset(0)
            self.assertEqual(self.lib.ew_images_load_document(url),-1)
            self.assertEqual(self.lib.ew_source_byte(0),0)
            self.assertEqual(self.lib.ew_fetch_document(url,final,error,128,None),len(body))
            self.assertEqual(self.lib.ew_images_load_document(url),0)

if __name__=='__main__':unittest.main()
