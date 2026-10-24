"""Differential GIF tests against Pillow; tests the production C decoder.

Run with a Python containing Pillow:
  python3 image/tests/test_gif.py
The script builds a temporary shared library and leaves the source tree clean.
"""
import ctypes
import io
from pathlib import Path
import random
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BAYER = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


class Gif(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint), ("height", ctypes.c_uint),
                ("stride", ctypes.c_uint),
                ("pixels", ctypes.POINTER(ctypes.c_ubyte)),
                ("opacity", ctypes.POINTER(ctypes.c_ubyte))]


def encoded(width, height, count, seed, interlaced=False, transparent=None):
    rng = random.Random(seed)
    im = Image.new("P", (width, height))
    colors = [component for i in range(256)
              for component in ((i * 73) % 256, (i * 151) % 256, (i * 199) % 256)]
    colors[:6] = [0, 0, 0, 255, 255, 255]
    im.putpalette(colors)
    im.putdata([rng.randrange(count) for _ in range(width * height)])
    stream = io.BytesIO()
    options = {"interlace": interlaced, "optimize": False}
    if transparent is not None:
        options["transparency"] = transparent
    im.save(stream, format="GIF", **options)
    return stream.getvalue()


def local_palette(blob):
    """Move a generated global palette to its first image descriptor."""
    flags = blob[10]
    length = 3 * (2 << (flags & 7))
    colors = blob[13:13 + length]
    result = bytearray(blob[:13] + blob[13 + length:])
    result[10] &= 0x7f
    pos = 13
    while result[pos] == 0x21:
        pos += 2
        while result[pos]:
            pos += result[pos] + 1
        pos += 1
    assert result[pos] == 0x2c
    result[pos + 9] |= flags & 0x87
    return bytes(result[:pos + 10] + colors + result[pos + 10:])


def main():
    with tempfile.TemporaryDirectory(prefix="elksweb-gif-test-") as directory:
        shared = Path(directory) / "gif.so"
        subprocess.run(["cc", "-std=c89", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", str(ROOT / "gif.c"), "-o", str(shared)], check=True)
        lib = ctypes.CDLL(str(shared))
        lib.ew_gif_decode.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(Gif)]
        lib.ew_gif_decode.restype = ctypes.c_int
        lib.ew_gif_free.argtypes = [ctypes.POINTER(Gif)]
        lib.ew_gif_decode_aspect.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                            ctypes.POINTER(Gif), ctypes.c_uint]

        def decode(blob):
            result = Gif()
            status = lib.ew_gif_decode(blob, len(blob), ctypes.byref(result))
            return status, result

        cases = 0
        for width, height, colors in [(1, 1, 2), (9, 7, 2), (32, 31, 4),
                                       (128, 128, 256), (256, 256, 2), (640, 480, 2)]:
            for interlaced in (False, True):
                for transparent in (None, 0):
                    blob = encoded(width, height, colors, cases, interlaced, transparent)
                    # Alternate global/local color tables while preserving
                    # the independently decoded expected image.
                    if cases & 1:
                        blob = local_palette(blob)
                    status, output = decode(blob)
                    assert status == 0, (width, height, interlaced, transparent, status)
                    reference = Image.open(io.BytesIO(blob)).convert("RGBA")
                    assert (output.width, output.height) == reference.size
                    for y in range(height):
                        for x in range(width):
                            r, g, b, a = reference.getpixel((x, y))
                            offset, mask = y * output.stride + x // 8, 128 >> (x & 7)
                            opaque = bool(output.opacity[offset] & mask) if output.opacity else True
                            assert opaque == bool(a), ("alpha", x, y)
                            if a:
                                gray = (r * 77 + g * 150 + b * 29) >> 8
                                expected = gray > BAYER[(y & 3) * 4 + (x & 3)] * 16 + 7
                                assert bool(output.pixels[offset] & mask) == expected, ("pixel", x, y)
                    lib.ew_gif_free(ctypes.byref(output))
                    assert not output.pixels and not output.opacity
                    cases += 1

        # Full frames can skip logical-screen background emission, but offset
        # frames must retain it. Use white background so zeroing alone fails.
        for partial in (False, True):
            for transparent in (None, 0):
                blob = bytearray(encoded(9, 7, 2, 42, transparent=transparent))
                blob[11] = 1
                if partial:
                    pos = 13 + 3 * (2 << (blob[10] & 7))
                    while blob[pos] == 0x21:
                        pos += 2
                        while blob[pos]:
                            pos += blob[pos] + 1
                        pos += 1
                    assert blob[pos] == 0x2c
                    blob[6:10] = (15).to_bytes(2, "little") + (12).to_bytes(2, "little")
                    blob[pos+1:pos+5] = (3).to_bytes(2, "little") + (2).to_bytes(2, "little")
                blob = bytes(blob)
                reference = Image.open(io.BytesIO(blob)).convert("RGBA")
                for aspect in (1, 2):
                    output = Gif()
                    assert lib.ew_gif_decode_aspect(blob, len(blob), ctypes.byref(output), aspect) == 0
                    for y in range(output.height):
                        for x in range(output.width):
                            at, mask = y * output.stride + x // 8, 128 >> (x & 7)
                            outside = partial and not (3 <= x < 12 and 2 <= y < 9)
                            if outside:
                                # The decoder preserves background color bits even
                                # when the first-frame transparency mask hides them.
                                assert output.pixels[at] & mask
                                if transparent is None: assert not output.opacity
                                if transparent is not None:
                                    assert not (output.opacity[at] & mask)
                                continue
                            r, g, b, a = reference.getpixel((x, y))
                            opaque = bool(output.opacity[at] & mask) if output.opacity else True
                            assert opaque == bool(a)
                            if opaque:
                                gray = (r * 77 + g * 150 + b * 29) >> 8
                                expected = gray > BAYER[((y // aspect) & 3) * 4 + (x & 3)] * 16 + 7
                                assert bool(output.pixels[at] & mask) == expected
                    lib.ew_gif_free(ctypes.byref(output))
                    cases += 1

        minimal = encoded(1, 1, 2, 0)
        # Trailer is not required after a complete first frame, but its data
        # sub-block terminator is required. Reject every earlier truncation.
        for end in range(len(minimal) - 1):
            status, output = decode(minimal[:end])
            assert status != 0, ("truncation accepted", end)
            assert not output.pixels and not output.opacity
        for header in (b"NOTGIF", b"GIF90a"):
            status, output = decode(header + minimal[6:])
            assert status == 1 and not output.pixels
        oversized = bytearray(minimal)
        oversized[6:8] = (641).to_bytes(2, "little")
        assert decode(bytes(oversized))[0] == 2

        # Deterministic malformed-input smoke: no crash, no leaked successful
        # output, no failed-call output pointers. Full sanitizer harness can
        # exercise this same corpus independently.
        rng = random.Random(2601)
        for _ in range(1000):
            blob = bytearray(minimal)
            for _ in range(rng.randrange(1, 8)):
                blob[rng.randrange(len(blob))] = rng.randrange(256)
            status, output = decode(bytes(blob))
            if status == 0:
                lib.ew_gif_free(ctypes.byref(output))
            else:
                assert not output.pixels and not output.opacity
        print(f"GIF differential tests passed: {cases} images, all minimal-file truncations, 1000 mutations")


if __name__ == "__main__":
    main()
