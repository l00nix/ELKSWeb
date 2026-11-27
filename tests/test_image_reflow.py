"""Image reflow skips unneeded parses and matches a fresh full parse."""
import ctypes as C, pathlib, subprocess, tempfile, unittest
HERE=pathlib.Path(__file__).resolve().parent
SRC=HERE.parent/'src'
GIF=str((HERE/'fixtures/image.gif').resolve()).encode()
TABLE=b'<table border=1 width=280 cellpadding=2 cellspacing=2><tr><td>Label</td><td>One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen.</td></tr></table>'
class Reflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='elksweb-reflow-qa-');library=pathlib.Path(cls.temp.name)/'core.so'
        sources=[SRC/(s+'.c') for s in ('html','url','net','images')]+[HERE.parent/'font/font.c',HERE.parent/'font/body_font.c',HERE.parent/'image/gif.c',HERE.parent/'image/dimensions.c',HERE/'qa_image_shim.c',HERE/'qa_fault_memory.c',HERE/'qa_layout_digest.c']
        subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-DEW_QA_REAL_IMAGES','-Wl,--wrap=ew_document_reset','-I'+str(SRC),'-I'+str(HERE.parent/'font'),'-I'+str(HERE.parent/'platform'),*[str(s) for s in sources],'-o',str(library)],check=True,capture_output=True)
        cls.lib=C.CDLL(str(library));cls.lib.ew_fetch_document.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p];cls.lib.ew_fetch_document.restype=C.c_int32
        cls.lib.ew_parse_source.argtypes=[C.c_char_p];cls.lib.ew_reflow_source.argtypes=[C.c_char_p]
        cls.lib.qa_layout_digest.restype=C.c_uint64
        cls.reflow=C.c_int.in_dll(cls.lib,'ew_image_reflow')
    @classmethod
    def tearDownClass(cls):cls.lib.ew_images_clear();cls.lib.ew_source_free();cls.temp.cleanup()
    def setUp(self):self.lib.ew_images_clear();self.lib.ew_source_free();self.lib.qa_io_reset(0);self.lib.qa_allocator_reset(0)
    def load(self,html):
        """Mirror main.c load(): parse, load images, reflow only when needed."""
        self.source=tempfile.NamedTemporaryFile();self.addCleanup(self.source.close)
        self.source.write(html);self.source.flush();self.name=self.source.name.encode()
        final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
        self.assertEqual(self.lib.ew_fetch_document(self.name,final,error,128,None),len(html))
        self.lib.ew_images_clear();self.lib.qa_parse_passes()
        self.lib.ew_parse_source(self.name);first=self.lib.qa_parse_passes()
        self.lib.ew_images_load()
        return first,bool(self.reflow.value),bool(self.lib.ew_images_resized())
    def assert_matches_full_parse(self):
        self.lib.ew_reflow_source(self.name);passes=self.lib.qa_parse_passes();reflowed=self.lib.qa_layout_digest()
        self.lib.ew_parse_source(self.name);self.lib.qa_parse_passes()
        self.assertEqual(reflowed,self.lib.qa_layout_digest())
        return passes
    def test_unsized_image_outside_table_reuses_table_plans(self):
        first,flag,resized=self.load(b'<p><img src="'+GIF+b'"></p>'+TABLE)
        self.assertEqual(first,2);self.assertTrue(flag);self.assertTrue(resized)
        self.assertEqual(self.assert_matches_full_parse(),1)
    def test_unsized_image_inside_table_measures_again(self):
        first,flag,resized=self.load(TABLE.replace(b'<td>Label',b'<td><img src="'+GIF+b'">Label'))
        self.assertEqual(first,2);self.assertTrue(resized)
        self.assertEqual(self.assert_matches_full_parse(),2)
    def test_failed_unsized_image_skips_reflow(self):
        first,flag,resized=self.load(b'<p><img src="/nonexistent/missing.gif" alt="gone"></p>'+TABLE)
        self.assertTrue(flag);self.assertFalse(resized)
    def test_sized_image_never_reflows(self):
        first,flag,resized=self.load(b'<p><img src="'+GIF+b'" width=16 height=16></p>'+TABLE)
        self.assertFalse(flag);self.assertFalse(resized)
    def test_partly_sized_image_reflows(self):
        first,flag,resized=self.load(b'<p><img src="'+GIF+b'" width=32></p>')
        self.assertTrue(flag);self.assertTrue(resized)
        self.assertEqual(self.assert_matches_full_parse(),1)
if __name__=='__main__':unittest.main()
