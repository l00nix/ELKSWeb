#!/usr/bin/env python3
"""Check status-strip pixel bounds in actual, non-inverted CGA screenshots.

This only checks geometry; the captured text still requires visual review.
Use a capture with the status bar enabled and a nonempty status/error message.
"""
import argparse
import json
import pathlib

from parity import normalize, read_ppm


def check(path):
    width, height, pixels = normalize(read_ppm(path.read_bytes()))
    assert (width, height) == (640, 200)
    counts = {
        str(y): sum(pixels[(y * width + x) * 3:(y * width + x + 1) * 3] != b'\xff\xff\xff'
                    for x in range(width))
        for y in range(192, 200)
    }
    separator = all(pixels[(192 * width + x) * 3:(192 * width + x + 1) * 3] == b'\x00\x00\x00'
                    for x in range(width))
    blank_bottom = counts['199'] == 0
    nonempty = any(counts[str(y)] for y in range(193, 199))
    return {'capture': str(path), 'nonwhite_pixels_per_row': counts,
            'separator_192_solid_black': separator, 'bottom_199_blank': blank_bottom,
            'message_present_rows_193_to_198': nonempty,
            'pass': separator and blank_bottom and nonempty,
            'scope': 'Pixel bounds only; readability and message correctness need visual review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', nargs='+', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    results = [check(path) for path in args.captures]
    args.output.write_text(json.dumps({'results': results, 'pass': all(r['pass'] for r in results)}, indent=2) + '\n')
    return 0 if all(r['pass'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
