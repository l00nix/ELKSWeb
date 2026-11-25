"""Download controls: write scope and full-frame equivalence in both clients."""
import ctypes as C
import unittest
import test_repaint_regions as repaint

class DownloadEditing:
    @classmethod
    def setUpClass(cls):
        repaint.RepaintRegions.setUpClass.__func__(cls)
        cls.lib.qa_download_filename.restype=C.c_char_p
        cls.lib.qa_download_name.argtypes=[C.c_char_p]
    @classmethod
    def tearDownClass(cls):repaint.RepaintRegions.tearDownClass.__func__(cls)
    setUp=repaint.RepaintRegions.setUp
    tearDown=repaint.RepaintRegions.tearDown
    prepare=repaint.RepaintRegions.prepare
    count=repaint.RepaintRegions.count
    reset=repaint.RepaintRegions.reset
    no_full_clear=repaint.RepaintRegions.no_full_clear
    download=repaint.RepaintRegions.download
    test_edit_only_controls=repaint.RepaintRegions.test_download_edit_only_paints_controls
    test_cancel_restores_page=repaint.RepaintRegions.test_download_progress_then_cancel_restores_page
    test_save_restores_page=repaint.RepaintRegions.test_download_save_restores_page_and_exact_binary
    def controls_only(self):
        self.no_full_clear()
        self.assertEqual(self.count(0,0,640,102),0)
        self.assertEqual(self.count(0,152,640,self.height),0)
        self.assertEqual(self.count(624,102,640,152),0)
        self.assertGreater(self.count(0,102,624,152),0)
        self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)
    def test_long_filename_themes_and_stale_caret(self):
        for height in (200,350,480):
            for color,inverted in ((0,0),(0,1),(1,0),(1,1)):
                with self.subTest(height=height,color=color,inverted=inverted):
                    self.prepare(height);self.download();self.lib.qa_download_style(color,inverted)
                    self.lib.qa_download_name(b'/mnt/'+b'a'*100+b'.bin')
                    for key in (2,ord('X'),3,4,0,5,6,7):
                        self.reset();self.lib.qa_download_key(key);self.controls_only()
                    self.reset();self.lib.qa_download_click_name();self.controls_only()
                    # Repeated deletion erases old text, caret and focus borders.
                    self.lib.qa_download_key(3)
                    for _ in range(110):
                        self.reset();self.lib.qa_download_key(4);self.controls_only()
                    self.assertEqual(self.lib.qa_download_filename(),b'')
    def test_escape_and_address_edit_leave_dialog(self):
        for key in (27,12):
            self.prepare();self.download();self.lib.qa_download_key(key)
            self.assertFalse(self.lib.qa_repaint_download())
            self.assertEqual(self.lib.qa_repaint_editing(),int(key==12))
            self.assertEqual(self.lib.qa_repaint_full_equivalence(),0)

class DirectDownloadEditing(DownloadEditing,unittest.TestCase):pass
class NanoXDownloadEditing(DownloadEditing,unittest.TestCase):defines=['-DELKSWEB_NANOX=1']
