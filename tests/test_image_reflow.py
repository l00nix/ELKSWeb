"""Reflow only when an image using natural dimensions acquired a size."""
import ctypes as C, pathlib, unittest
import test_image_integration as integration
HERE=pathlib.Path(__file__).resolve().parent
GIF=str((HERE/'fixtures/image.gif').resolve()).encode()
class Reflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        integration.Images.setUpClass();cls.lib=integration.Images.lib
        cls.lib.ew_images_resized.restype=C.c_int
        cls.reflow=C.c_int.in_dll(cls.lib,'ew_image_reflow')
    @classmethod
    def tearDownClass(cls):integration.Images.tearDownClass()
    def setUp(self):
        self.lib.ew_images_clear();self.lib.ew_source_free()
        self.lib.qa_io_reset(0);self.lib.qa_allocator_reset(0)
    def load(self,html):
        self.lib.ew_parse(html,b'/tmp/reflow.htm')
        self.lib.ew_images_load()
        return bool(self.reflow.value),bool(self.lib.ew_images_resized())
    def test_missing_unsized_image_skips_reflow(self):
        self.assertEqual(self.load(b'<p>Before</p><img src="/nonexistent/missing.gif"><p>After</p>'),(True,False))
    def test_sized_image_never_reflows(self):
        self.assertEqual(self.load(b'<img src="'+GIF+b'" width=16 height=16>'),(False,False))
    def test_unsized_image_reflows(self):
        self.assertEqual(self.load(b'<img src="'+GIF+b'">'),(True,True))
    def test_partly_sized_image_reflows(self):
        self.assertEqual(self.load(b'<img src="'+GIF+b'" width=32>'),(True,True))
    def test_unsized_image_inside_table_still_reflows(self):
        self.assertEqual(self.load(b'<table><tr><td><img src="'+GIF+b'"></td></tr></table>'),(True,True))
    def test_sized_success_does_not_mask_unsized_failure(self):
        self.assertEqual(self.load(b'<img src="'+GIF+b'" width=16 height=16><img src="/nonexistent/missing.gif">'),(True,False))
if __name__=='__main__':unittest.main()
