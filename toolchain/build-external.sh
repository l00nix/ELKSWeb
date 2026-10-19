#!/bin/sh
# Minimal runtime build for ELKS buildext.sh and prepared developer trees.
set -eu

TOPDIR=${ELKSWEB_ELKS:-${TOPDIR:-}}
: "${TOPDIR:?Set TOPDIR or ELKSWEB_ELKS to a built ELKS checkout}"
export TOPDIR
PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
export PATH
app_root=${ELKSWEB_SOURCE:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}
cd "$app_root"

command -v ia16-elf-gcc >/dev/null
command -v elf2elks >/dev/null
mkdir -p build/obj
# Compile every source on each invocation; never install a stale executable.
rm -f build/elksweb build/obj/*.o build/obj/*.su
cflags='-march=i8086 -mtune=i8086 -mcmodel=small -melks-libc
    -mno-segment-relocation-stuff -Os -Wall -Wextra
    -fno-builtin-printf -fno-builtin-fprintf -I./src -I./platform -I./font'
set --
for source in src/*.c platform/*.c image/*.c font/*.c; do
    object=build/obj/$(printf '%s' "${source%.c}" | tr / _).o
    # cflags is a fixed list of compiler options, intentionally word-split.
    ia16-elf-gcc $cflags -c "$source" -o "$object"
    set -- "$@" "$object"
done
ia16-elf-gcc $cflags -Wl,-Map,build/elksweb.map "$@" -o build/elksweb
printf '%s\n' 'ELKSWeb runtime built: build/elksweb'
