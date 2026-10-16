"""Natural-size CGA dither regression; independent RGB/Pillow pixel oracle.

This validates destination-row dither phase, not area filtering or animation.
Run with the workspace Python (Pillow) to execute all cases.
"""
import ctypes as C
import io
import pathlib
import subprocess
import tempfile
import unittest
try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = pathlib.Path(__file__).resolve().parents[1]
BAYER = (0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5)

class Gif(C.Structure):
    _fields_ = [('width',C.c_uint),('height',C.c_uint),('stride',C.c_uint),
                ('pixels',C.POINTER(C.c_ubyte)),('opacity',C.POINTER(C.c_ubyte))]

@unittest.skipIf(Image is None, 'Independent GIF pixel oracle requires Pillow')
class GifAspect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-gif-aspect-')
        library = pathlib.Path(cls.temp.name)/'gif.so'
        subprocess.run(['cc','-std=c89','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        str(ROOT/'image/gif.c'),'-o',str(library)],check=True,capture_output=True)
        cls.lib = C.CDLL(str(library))
        cls.lib.ew_gif_decode.argtypes = [C.c_void_p,C.c_uint,C.POINTER(Gif)]
        cls.lib.ew_gif_decode_aspect.argtypes = [C.c_void_p,C.c_uint,C.POINTER(Gif),C.c_uint]
        cls.lib.ew_gif_free.argtypes = [C.POINTER(Gif)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def encoded(self,values,width,height,transparent=None,interlaced=False):
        picture=Image.new('P',(width,height))
        picture.putpalette([v for i in range(256) for v in (i,i,i)])
        picture.putdata(values)
        stream=io.BytesIO()
        args={'format':'GIF','optimize':False,'interlace':interlaced}
        if transparent is not None:args['transparency']=transparent
        picture.save(stream,**args)
        return stream.getvalue()

    def decode(self,blob,aspect):
        image=Gif()
        status=self.lib.ew_gif_decode_aspect(blob,len(blob),C.byref(image),aspect)
        self.assertEqual(status,0)
        try:
            pixels=C.string_at(image.pixels,image.stride*image.height)
            opacity=C.string_at(image.opacity,image.stride*image.height) if image.opacity else None
            return image.width,image.height,image.stride,pixels,opacity
        finally:self.lib.ew_gif_free(C.byref(image))

    def check_render(self,blob,aspect):
        width,height,stride,pixels,opacity=self.decode(blob,aspect)
        rgba=Image.open(io.BytesIO(blob)).convert('RGBA')
        self.assertEqual((width,height),rgba.size)
        rows=[]
        for y in range(max(1,height//aspect)):
            sy=y*height//max(1,height//aspect)
            row=[]
            for x in range(width):
                red,green,blue,alpha=rgba.getpixel((x,sy))
                at=sy*stride+x//8;mask=128>>(x&7)
                opaque=bool(opacity[at]&mask) if opacity else True
                self.assertEqual(opaque,bool(alpha),(x,y,'alpha'))
                if opaque:
                    gray=(red*77+green*150+blue*29)>>8
                    expected=gray>BAYER[((sy//aspect)&3)*4+(x&3)]*16+7
                    self.assertEqual(bool(pixels[at]&mask),expected,(x,y,'pixel'))
                row.append(int(bool(pixels[at]&mask)) if opaque else 1)
            rows.append(row)
        return rows

    def test_half_gray_is_checkerboard_after_two_to_one_reduction(self):
        rows=self.check_render(self.encoded([128]*128,8,16),2)
        self.assertEqual(rows,[[int((x+y)%2==0) for x in range(8)] for y in range(8)])

    def test_gray_patch_density_survives_cga_sampling(self):
        for gray,white in ((0,0),(64,16),(128,32),(192,48),(255,64)):
            rows=self.check_render(self.encoded([gray]*128,8,16),2)
            self.assertEqual(sum(map(sum,rows)),white,gray)

    def test_interlace_transparency_gradient_and_odd_dimensions(self):
        for interlaced in (False,True):
            for width,height in ((32,32),(31,33)):
                blob=self.encoded([(x*7+y*13)%256 for y in range(height) for x in range(width)],
                                  width,height,transparent=0,interlaced=interlaced)
                self.check_render(blob,1)
                self.check_render(blob,2)

    def test_black_white_pixels_and_opacity_unchanged(self):
        blob=self.encoded([0 if (x+y)%3 else 255 for y in range(32) for x in range(32)],
                          32,32,transparent=0,interlaced=True)
        self.assertEqual(self.decode(blob,1),self.decode(blob,2))

    def test_default_api_preserves_square_pixel_output(self):
        blob=self.encoded([i%256 for i in range(1024)],32,32)
        width,height,stride,pixels,opacity=self.decode(blob,1)
        image=Gif()
        self.assertEqual(self.lib.ew_gif_decode(blob,len(blob),C.byref(image)),0)
        try:self.assertEqual(C.string_at(image.pixels,stride*height),pixels)
        finally:self.lib.ew_gif_free(C.byref(image))

    def test_actual_frog_first_frame_rendered_pixel_oracle(self):
        blob=(ROOT/'tests/fixtures/frogfind/frog.gif').read_bytes()
        self.assertEqual(Image.open(io.BytesIO(blob)).size,(174,80))
        self.check_render(blob,2)
        self.check_render(blob,1)

    def test_invalid_aspect_is_rejected_with_empty_output(self):
        blob=self.encoded([128]*16,4,4)
        for aspect in (0,3,65535):
            image=Gif()
            self.assertNotEqual(self.lib.ew_gif_decode_aspect(blob,len(blob),C.byref(image),aspect),0)
            self.assertFalse(image.pixels)
            self.assertFalse(image.opacity)
            self.assertEqual(image.width,0)

if __name__=='__main__':unittest.main()
