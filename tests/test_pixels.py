"""Small format/normalization tests, independent of browsers."""
import unittest, tempfile, pathlib, types, json
from parity import read_ppm, normalize, compare_pixels, make_comparison

class Pixels(unittest.TestCase):
    def test_ppm_preserves_whitespace_pixel(self):
        self.assertEqual(read_ppm(b'P6\n1 1\n255\n\x0a\x20\x00'), (1,1,b'\x0a\x20\x00'))
    def test_exact_row_doubling_only(self):
        row=b'\x00'*1920
        self.assertEqual(normalize((640,400,row*400))[0:2], (640,200))
        altered=bytearray(row*400);altered[1920]=1
        with self.assertRaises(ValueError):normalize((640,400,bytes(altered)))
    def test_mismatch_is_failure(self):
        self.assertEqual(compare_pixels((1,1,b'\x00\x00\x00'),(1,1,b'\x00\x01\x00'))['different_pixels'],1)
    def test_geometry_is_failure(self):
        self.assertFalse(compare_pixels((1,1,b'\x00'*3),(2,1,b'\x00'*6))['same_geometry'])
    def test_blind_artifact_and_diff_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)
            a=b'\0'*(640*200*3);b=bytearray(a);b[0]=255
            (out/'a.ppm').write_bytes(b'P6\n640 200\n255\n'+a)
            (out/'b.ppm').write_bytes(b'P6\n640 200\n255\n'+b)
            ref={'case':{'captures':{'initial':{'ppm':'a.ppm'}}}}
            cand={'case':{'captures':{'initial':{'ppm':'b.ppm'}}}}
            result=make_comparison(types.SimpleNamespace(output=out),ref,cand)
            self.assertFalse(result[0]['pass']);self.assertEqual(result[0]['different_pixels'],1)
            key=json.loads((out/'comparison/blind-key.json').read_text())['case-initial']
            self.assertEqual(set(key.values()),{'reference','candidate'})
            self.assertTrue((out/'comparison/case-initial-blind.png').read_bytes().startswith(b'\x89PNG'))
    def test_missing_candidate_capture_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=make_comparison(types.SimpleNamespace(output=pathlib.Path(tmp)),{'case':{'captures':{'initial':{}}}}, {})
            self.assertFalse(result[0]['pass']);self.assertIn('missing',result[0]['error'])

if __name__=='__main__':unittest.main()
