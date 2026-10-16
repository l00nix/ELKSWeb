#!/usr/bin/env python3
"""Preserve the linked ELF before the native converter replaces it in place."""
import os
import pathlib
import shutil
import sys

for argument in sys.argv[1:]:
    path = pathlib.Path(argument)
    if path.is_file():
        with path.open('rb') as stream:
            if stream.read(4) == b'\x7fELF':
                shutil.copyfile(path, str(path) + '.elf')
                break
real = os.environ['ELKSWEB_REAL_ELF2ELKS']
os.execv(real, [real] + sys.argv[1:])
