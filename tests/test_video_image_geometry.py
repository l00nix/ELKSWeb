"""Image layout/map geometry when the runtime display changes aspect policy."""
import ctypes as C
import unittest
import test_image_alt

class VideoImageGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_image_alt.ImageAlt.setUpClass()
        cls.lib = test_image_alt.ImageAlt.lib
        cls.lib.ew_parse_image_source.argtypes = [C.c_char_p]

    @classmethod
    def tearDownClass(cls):
        test_image_alt.ImageAlt.tearDownClass()

    def setUp(self):
        self.lib.ew_images_clear()

    def tearDown(self):
        self.geometry(200, 2)

    def geometry(self, height, aspect):
        C.c_int.in_dll(self.lib, 'ew_screen_height').value = height
        C.c_int.in_dll(self.lib, 'ew_pixel_aspect').value = aspect

    def parse_image(self, html):
        self.lib.ew_parse(html, b'http://host/page')
        return next(i for i in range(self.lib.qa_runs()) if self.lib.qa_run_kind(i) == 5)

    def test_explicit_image_height_and_missing_map_coordinates(self):
        for screen, aspect in ((200, 2), (350, 1), (480, 1)):
            self.geometry(screen, aspect)
            i = self.parse_image(b'<a href="/map"><img src="missing.gif" width=100 height=80 ismap></a>')
            self.assertEqual(self.lib.qa_run_width_field(i), 80//aspect)
            mx, my = C.c_uint(), C.c_uint()
            self.assertEqual(self.lib.alt_point(i, 30, 20, C.byref(mx), C.byref(my)), 0)
            self.assertEqual((mx.value, my.value), (30, 20*aspect))

    def test_direct_image_uses_selected_aspect(self):
        for screen, aspect in ((200, 2), (350, 1), (480, 1)):
            self.geometry(screen, aspect)
            self.lib.ew_parse_image_source(b'http://host/missing.gif')
            self.assertEqual(self.lib.qa_run_length(0), 64)
            self.assertEqual(self.lib.qa_run_width_field(0), 64//aspect)

    def test_image_height_cap_preserves_byte_metadata(self):
        for screen, aspect in ((200, 2), (350, 1), (480, 1)):
            self.geometry(screen, aspect)
            i = self.parse_image(b'<img src="missing.gif" width=100 height=400>')
            self.assertEqual(self.lib.qa_run_width_field(i), 200)
            self.assertFalse(self.lib.qa_truncated())

    def test_cached_map_coordinates_still_use_natural_dimensions(self):
        src = ('file://' + str((test_image_alt.ROOT/'tests/fixtures/image.gif').resolve())).encode()
        html = b'<a href="/map"><img src="'+src+b'" width=32 height=64 ismap></a>'
        self.parse_image(html)
        self.lib.ew_images_load()
        for screen, aspect in ((200, 2), (350, 1), (480, 1)):
            self.geometry(screen, aspect)
            i = self.parse_image(html)
            mx, my = C.c_uint(), C.c_uint()
            self.assertEqual(self.lib.alt_point(i, 16, 32//aspect, C.byref(mx), C.byref(my)), 0)
            self.assertEqual((mx.value, my.value), (8, 8))

if __name__ == '__main__': unittest.main()
