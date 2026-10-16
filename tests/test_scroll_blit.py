"""Compare actual-main incremental scrolling with complete rendering of its state.

The framebuffer copy here is a logical-pixel oracle, deliberately independent of
CGA banking. platform/tests/test_scroll.py checks actual driver's bytes. These
are correctness/write-region checks, not hardware speed or visual parity claims.
"""
import pathlib
import tempfile
import unittest
import test_repaint_regions as repaint

ROOT = pathlib.Path(__file__).resolve().parents[1]
GIF = ROOT / 'tests/fixtures/image.gif'
CHUNK = (b'<p><b>Bold</b> <i>italic</i> <u>underlined</u> <small>small</small> '
         b'<a href="next.htm">linked words</a></p>'
         b'<table border=1><tr><td>border</td><td>another cell</td></tr></table>'
         b'<form><input name=q value="field text"><input type=checkbox checked>'
         b'<input type=radio name=r checked><select name=s><option>Alpha</option>'
         b'<option>Beta</option></select><input type=submit value=Send></form>'
         b'<img src="' + str(GIF).encode() + b'" width=39 height=37>'
         b'<img src="' + str(GIF).encode() + b'" width=7 height=9><hr>')
PAGE = b'<title>Scroll oracle</title>' + CHUNK * 20


class ScrollBlit(unittest.TestCase):
    setUpClass = classmethod(repaint.RepaintRegions.setUpClass.__func__)
    tearDownClass = classmethod(repaint.RepaintRegions.tearDownClass.__func__)
    setUp = repaint.RepaintRegions.setUp
    tearDown = repaint.RepaintRegions.tearDown
    prepare = repaint.RepaintRegions.prepare
    reset = repaint.RepaintRegions.reset
    count = repaint.RepaintRegions.count
    download = repaint.RepaintRegions.download

    def mixed(self, height):
        self.prepare(height)
        with tempfile.NamedTemporaryFile(suffix='.htm') as page:
            page.write(PAGE); page.flush()
            self.assertEqual(self.lib.qa_repaint_load(('file:'+page.name).encode()), 1)
        self.assertGreater(self.lib.qa_scroll_loaded_images(), 0,
                           'Fixture must exercise decoded GIFs, not just placeholders')
        self.reset()

    def equal_full(self):
        self.assertEqual(self.lib.qa_repaint_full_equivalence(), 0,
                         'Incremental framebuffer differs from complete redraw')

    def move(self, target):
        self.lib.qa_scroll_move(target)
        self.lib.qa_scroll_flush()

    def test_mixed_document_both_directions_and_odd_rows(self):
        for height in (200, 350, 480):
            with self.subTest(height=height):
                self.mixed(height)
                self.move(500); self.equal_full()
                view = height - 30
                for delta in (1, -1, 3, -3, 10, -10, 17, -17, view-1, 1-view):
                    with self.subTest(height=height, delta=delta):
                        before = self.lib.qa_scroll_position(); self.reset()
                        self.move(before + delta)
                        self.assertEqual(self.lib.qa_scroll_copies(), 1)
                        self.assertEqual(self.lib.qa_scroll_delta(), delta)
                        self.assertEqual(self.lib.qa_scroll_top(), 22)
                        self.assertEqual(self.lib.qa_scroll_bottom(), height-8)
                        self.assertEqual(self.count(0, 0, 640, 22), 0)
                        if delta > 0:
                            self.assertEqual(self.count(0, 22, 624, height-8-delta), 0)
                            self.assertGreater(self.count(0, height-8-delta, 624, height-8), 0)
                        else:
                            self.assertEqual(self.count(0, 22-delta, 624, height-8), 0)
                            self.assertGreater(self.count(0, 22, 624, 22-delta), 0)
                        self.equal_full()

    def test_missing_image_alt_crossing_viewport_and_exposed_strip(self):
        html=(b'<p>Before image</p><img src="missing.gif" width=180 height=40 '
              b'alt="Missing image description"><p>After image</p>')*20
        for height in (200,350,480):
            self.prepare(height,html)
            for target in list(range(1,121))+list(range(119,0,-1)):
                with self.subTest(height=height, target=target):
                    self.move(target); self.equal_full()

    def test_arrow_page_keys_and_mouse_drag_use_scroll_path(self):
        for height in (200, 350, 480):
            self.mixed(height); self.move(500); self.equal_full()
            for action in (0, 1, 2, 3):
                with self.subTest(height=height, action=action):
                    self.reset(); self.lib.qa_scroll_queue_key(action); self.lib.qa_scroll_flush()
                    self.assertEqual(self.lib.qa_scroll_copies(), 1)
                    self.equal_full()
            # Drag near the current thumb produces a real mouse-driven movement.
            self.reset(); self.lib.qa_scroll_drag_step(2); self.lib.qa_scroll_flush()
            self.assertGreater(self.lib.qa_scroll_position(), 500)
            self.assertEqual(self.lib.qa_scroll_copies(), 1)
            self.equal_full()

    def test_pending_focus_editor_invert_horizontal_damage_forces_full_page(self):
        for action in (4, 5, 7, 9):
            with self.subTest(action=action):
                self.mixed(200); self.move(100); self.equal_full(); self.reset()
                self.lib.qa_scroll_queue_key(action)
                self.move(103)
                self.assertEqual(self.lib.qa_scroll_copies(), 0)
                self.equal_full()

    def test_large_jumps_and_geometry_changes_fall_back(self):
        for height in (200, 350, 480):
            for delta in (height-30, height+1):
                with self.subTest(height=height, delta=delta):
                    self.mixed(height); self.reset(); self.move(delta)
                    self.assertEqual(self.lib.qa_scroll_copies(), 0); self.equal_full()
            self.reset(); self.lib.qa_scroll_queue_key(8); self.move(101)
            self.assertEqual(self.lib.qa_scroll_copies(), 0); self.equal_full()
            # Once hidden bars have been fully painted, normal scrolling can copy.
            self.reset(); self.move(104)
            self.assertEqual(self.lib.qa_scroll_copies(), 1); self.equal_full()

    def test_open_dropdown_and_download_do_not_copy(self):
        self.mixed(200); self.lib.qa_scroll_open_select(); self.lib.qa_scroll_flush()
        self.reset(); self.move(3)
        self.assertEqual(self.lib.qa_scroll_copies(), 0); self.equal_full()
        self.prepare(200); self.download(); self.reset(); self.move(3)
        self.assertEqual(self.lib.qa_scroll_copies(), 0); self.equal_full()

    def test_navigation_resets_copy_origin_then_scrolls_new_page(self):
        self.mixed(200); self.move(500); self.equal_full(); self.reset()
        with tempfile.NamedTemporaryFile(suffix='.htm') as page:
            page.write(b'<title>New page</title>'+CHUNK*12); page.flush()
            self.assertEqual(self.lib.qa_repaint_load(('file:'+page.name).encode()), 1)
        self.assertEqual(self.lib.qa_scroll_copies(), 0)
        self.assertEqual(self.lib.qa_scroll_position(), 0); self.equal_full()
        self.reset(); self.move(3)
        self.assertEqual(self.lib.qa_scroll_copies(), 1); self.equal_full()

    def test_accumulated_scroll_and_reversal_use_last_painted_origin(self):
        self.mixed(200); self.move(500); self.equal_full(); self.reset()
        for target in (507, 491, 515): self.lib.qa_scroll_move(target)
        self.lib.qa_scroll_flush()
        self.assertEqual(self.lib.qa_scroll_copies(), 1)
        self.assertEqual(self.lib.qa_scroll_delta(), 15); self.equal_full()
        self.reset()
        for target in (517, 515): self.lib.qa_scroll_move(target)
        self.lib.qa_scroll_flush()
        self.assertEqual(self.lib.qa_scroll_copies(), 0); self.equal_full()


if __name__ == '__main__': unittest.main()
