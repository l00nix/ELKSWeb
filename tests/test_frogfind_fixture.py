"""Fixture integrity, localhost delivery and independent first-frame GIF pixels."""
import ctypes as C
import hashlib
import html.parser
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import urllib.request
from parity import FixtureServer, FROG_FILES, FIXTURES, CASES

FROG=FIXTURES/'frogfind'
class References(html.parser.HTMLParser):
    def __init__(self): super().__init__(); self.refs=[]
    def handle_starttag(self,tag,attrs):
        self.refs.extend(v for k,v in attrs if k in ('href','src','action') and v)

class FrogFixture(unittest.TestCase):
    def test_provenance_and_relative_resources(self):
        metadata=json.loads((FROG/'PROVENANCE.json').read_text())
        self.assertEqual(hashlib.sha256((FROG/'frog.gif').read_bytes()).hexdigest(),metadata['image_sha256'])
        self.assertFalse(metadata['image_modified'])
        for name in FROG_FILES:
            self.assertTrue((FROG/name).is_file())
            if name.endswith('.htm'):
                refs=References();refs.feed((FROG/name).read_text())
                for ref in refs.refs:
                    if ':' not in ref: self.assertTrue((FROG/ref.split('?',1)[0]).is_file(),(name,ref))
        self.assertIn('q=ELKS',CASES['frogfind_http']['exact_requests'][0]['path'])

    def test_http_form_result_gif_and_article(self):
        server=FixtureServer(0)
        try:
            base='http://127.0.0.1:'+str(server.server.server_port)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for route,name in [('http.htm','http.htm'),('frog.gif','frog.gif'),('results.htm?q=ELKS','results.htm'),('article.htm','article.htm')]:
                with opener.open(base+'/frogfind/'+route,timeout=2) as response:
                    self.assertEqual(response.read(),(FROG/name).read_bytes())
                    self.assertEqual(response.headers.get_content_type(),'image/gif' if name.endswith('.gif') else 'text/html')
            self.assertTrue(any(r['path']=='/frogfind/results.htm?q=ELKS' for r in server.requests))
        finally: server.close()

    def test_actual_decoder_matches_independent_first_frame(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Optional first-frame pixel oracle requires Pillow')
        class Gif(C.Structure):
            _fields_=[('width',C.c_uint),('height',C.c_uint),('stride',C.c_uint),('pixels',C.POINTER(C.c_ubyte)),('opacity',C.POINTER(C.c_ubyte))]
        raw=(FROG/'frog.gif').read_bytes()
        with tempfile.TemporaryDirectory(prefix='frog-gif-qa-') as tmp:
            library=Path(tmp)/'gif.so'
            subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror',str(FIXTURES.parents[1]/'image/gif.c'),'-o',str(library)],check=True,capture_output=True)
            lib=C.CDLL(str(library));lib.ew_gif_decode.argtypes=[C.c_void_p,C.c_uint,C.POINTER(Gif)];lib.ew_gif_free.argtypes=[C.POINTER(Gif)]
            image=Gif();self.assertEqual(lib.ew_gif_decode(raw,len(raw),C.byref(image)),0)
            try:
                oracle=Image.open(io.BytesIO(raw));self.assertEqual(oracle.n_frames,2);oracle.seek(0);rgba=oracle.convert('RGBA')
                self.assertEqual((image.width,image.height),(174,80));transparent=0
                bayer=(0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5)
                for y in range(80):
                    for x in range(174):
                        r,g,b,a=rgba.getpixel((x,y));at=y*image.stride+x//8;mask=128>>(x&7)
                        self.assertEqual(bool(image.opacity[at]&mask) if image.opacity else True,bool(a),(x,y,'opacity'))
                        if a:self.assertEqual(bool(image.pixels[at]&mask),((r*77+g*150+b*29)>>8)>bayer[(y&3)*4+(x&3)]*16+7,(x,y,'pixel'))
                        else:transparent+=1
                self.assertGreater(transparent,0)
            finally: lib.ew_gif_free(C.byref(image))
