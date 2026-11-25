"""Mouse navigation must finish painting downloaded images on the first visit."""
import unittest
import test_repaint_regions as repaint
from test_core_regression import OneHTTP


class MouseImageNavigation:
    @classmethod
    def setUpClass(cls):
        repaint.RepaintRegions.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        repaint.RepaintRegions.tearDownClass.__func__(cls)

    setUp = repaint.RepaintRegions.setUp
    tearDown = repaint.RepaintRegions.tearDown
    prepare = repaint.RepaintRegions.prepare
    count = repaint.RepaintRegions.count

    def test_first_mouse_navigation_paints_sized_gif_without_full_page_repaint(self):
        gif = (repaint.ROOT / 'tests/fixtures/frogfind/frog.gif').read_bytes()
        page = (b'<title>FrogFind</title><p>FrogFind</p>'
                b'<img src="frog.gif" width=174 height=80 alt="Waiting frog">'
                b'<form><input name=q><input type=submit value=Go></form>')
        responses = [b'HTTP/1.0 200 OK\r\nContent-Type: ' + kind +
                     b'\r\nContent-Length: ' + str(len(body)).encode() +
                     b'\r\n\r\n' + body
                     for kind, body in [(b'text/html', page), (b'image/gif', gif)]]
        for height in (200, 350, 480):
            for trigger in ('link', 'image', 'submit'):
                with self.subTest(height=height, trigger=trigger):
                    server = OneHTTP(responses)
                    url = (server.url + '/index.htm').encode()
                    if trigger == 'submit':
                        html = b'<form action="' + url + b'"><input type=submit value=Go></form>'
                    else:
                        label = (b'<img src="missing.gif" width=24 height=24>'
                                 if trigger == 'image' else b'FrogFind')
                        html = b'<a href="' + url + b'">' + label + b'</a>'
                    try:
                        self.prepare(height, html)
                        self.lib.qa_focus_noimages(0)
                        self.lib.qa_repaint_click_link(0)
                    finally:
                        server.close()
                    self.assertEqual(len(server.requests), 2)
                    self.assertTrue(server.requests[1].startswith(b'GET /frog.gif '))
                    self.assertEqual(self.lib.qa_scroll_loaded_images(), 1)
                    self.assertEqual(self.lib.qa_address_status(), b'')
                    # Background below all content is painted only once.
                    self.assertEqual(self.count(0, height-38, 624, height-18), 624*20)
                    # A full repaint must not reveal a previously hidden frog.
                    self.assertEqual(self.lib.qa_repaint_full_equivalence(), 0)


class DirectMouseImages(MouseImageNavigation, unittest.TestCase):
    pass


class NanoXMouseImages(MouseImageNavigation, unittest.TestCase):
    defines = ['-DELKSWEB_NANOX']


if __name__ == '__main__':
    unittest.main()
