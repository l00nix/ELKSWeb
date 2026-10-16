"""Check actual CGA/EGA/VGA line bytes against an independent pixel model."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest

PLATFORM = Path(__file__).resolve().parents[1]


class HorizontalLine(unittest.TestCase):
    def test_clipped_lines_preserve_all_other_pixels(self):
        source = (PLATFORM / 'elks_platform.c').read_text()
        routines = source[source.index('static unsigned scan_offset'):
                          source.index('void ew_cursor_hide(void)')]
        with tempfile.TemporaryDirectory(prefix='ew-hline-') as directory:
            root = Path(directory)
            (root / 'line.c').write_text(
                '#include "elks_platform.h"\nunsigned char video[65536]={1};\n'
                'int ew_screen_height=200, ew_pixel_aspect=2;\n'
                'static unsigned video_bytes=16384;\n' +
                '\n'.join(line for line in source.splitlines()
                          if line.startswith('static int clip_')) + '\n' + routines)
            subprocess.run(['cc', '-O2', '-shared', '-fPIC', '-Wall', '-Wextra',
                            '-Werror', '-I'+str(PLATFORM), str(root / 'line.c'),
                            '-o', str(root / 'line.so')], check=True)
            library = C.CDLL(str(root / 'line.so'))
            video = (C.c_ubyte * 65536).in_dll(library, 'video')
            screen_height = C.c_int.in_dll(library, 'ew_screen_height')
            seed = bytes((i * 73 + i // 17) & 255 for i in range(65536))
            for height in (200, 350, 480):
                screen_height.value = height
                for x in list(range(-17, 18)) + list(range(625, 642)) + [-32768, 32767]:
                    for y in [-1, 0, 1, height-2, height-1, height]:
                        for width in list(range(-1, 18)) + [63, 640, 32767]:
                            for white in (0, 1):
                                expected = bytearray(seed)
                                if 0 <= y < height:
                                    for px in range(max(0, x), min(640, x + width)):
                                        row = (y % 2) * 8192 + (y // 2) * 80 if height == 200 else y * 80
                                        offset = row + px // 8
                                        mask = 128 >> (px % 8)
                                        if white: expected[offset] |= mask
                                        else: expected[offset] &= 255 ^ mask
                                C.memmove(video, seed, len(seed))
                                library.ew_hline(x, y, width, white)
                                self.assertEqual(bytes(video), expected, (height, x, y, width, white))


if __name__ == '__main__':
    unittest.main()
