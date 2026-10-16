"""Actual C metadata reader against independent Pillow images and malformed input."""
import ctypes as C
import io
from pathlib import Path
import random
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='elksweb-dimensions-') as tmp:
    libpath = Path(tmp) / 'dimensions.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    str(ROOT / 'dimensions.c'), '-o', str(libpath)], check=True)
    lib = C.CDLL(str(libpath))
    lib.ew_image_dimensions.argtypes = [C.c_void_p, C.c_uint,
                                        C.POINTER(C.c_uint), C.POINTER(C.c_uint)]
    def check(data, expected=None):
        buf = C.create_string_buffer(data)
        w, h = C.c_uint(0), C.c_uint(0)
        result = lib.ew_image_dimensions(buf, len(data), C.byref(w), C.byref(h))
        if expected is not None:
            assert result == 1 and (w.value, h.value) == expected, (result, w.value, h.value)
        elif result:
            assert 0 < w.value <= 65535 and 0 < h.value <= 65535
        return bool(result)
    fixtures = 0
    for kind in ('GIF', 'PNG', 'JPEG'):
        for size in ((1, 1), (16, 31), (320, 200), (640, 480)):
            for progressive in (False, True) if kind == 'JPEG' else (False,):
                out = io.BytesIO()
                Image.new('RGB', size, '#608020').save(out, kind, progressive=progressive)
                data = out.getvalue()
                check(data, size)
                fixtures += 1
                for n in range(len(data)):
                    check(data[:n])
    # Fake PNG IHDR with a dimension outside the 16-bit layout range.
    header = b'\x89PNG\r\n\x1a\n\0\0\0\rIHDR'
    check(header + (100000).to_bytes(4, 'big') + (200).to_bytes(4, 'big'), (65535, 200))
    assert not check(header + b'\0' * 8)
    for malformed in (b'\xff\xd8\xff\xe0\0\0', b'\xff\xd8\xff\xe0\xff\xff',
                      b'\xff\xd8\xff\xc0\0\x08\x08\0\x10\0\x10\0',
                      b'\xff\xd8\xff\xda\0\x08abcdef'):
        assert not check(malformed)
    rng = random.Random(8088)
    for _ in range(5000):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(256)))
        check(data)
    print(f'Dimensions PASS: {fixtures} Pillow fixtures, every prefix, 5000 random inputs')
