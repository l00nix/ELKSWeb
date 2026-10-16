#!/usr/bin/env bash
# Run against native ELKS ia16 GCC, keeping all output in the private tree.
set -euo pipefail
: "${ELKSWEB_ELKS:?Set ELKSWEB_ELKS to an isolated, built ELKS checkout}"
export TOPDIR="$ELKSWEB_ELKS"
export PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
app_root=${ELKSWEB_SOURCE:-$(cd "$(dirname "$0")/.." && pwd)}
mkdir -p "$app_root/build"
cd "$app_root"
mkdir -p build/host-tools
cp toolchain/retain-elf2elks.py build/host-tools/elf2elks
chmod +x build/host-tools/elf2elks
export ELKSWEB_REAL_ELF2ELKS="$TOPDIR/elks/tools/bin/elf2elks"
export PATH="$app_root/build/host-tools:$PATH"
cflags=(-march=i8086 -mtune=i8086 -mcmodel=small -melks-libc
    -mno-segment-relocation-stuff -Os -Wall -Wextra -fstack-usage
    -fno-builtin-printf -fno-builtin-fprintf -I./src -I./platform -I./font)
mkdir -p build/obj
rm -f build/obj/*.o build/obj/*.su
: > build/compiler-command.txt
objects=()
for source in src/*.c platform/*.c image/*.c font/*.c; do
    object="build/obj/${source//\//_}"
    object="${object%.c}.o"
    printf '%q ' ia16-elf-gcc "${cflags[@]}" -c "$source" -o "$object" >> build/compiler-command.txt
    printf '\n' >> build/compiler-command.txt
    ia16-elf-gcc "${cflags[@]}" -c "$source" -o "$object"
    objects+=("$object")
done
printf '%q ' ia16-elf-gcc "${cflags[@]}" -Wl,-Map,build/elksweb.map "${objects[@]}" -o build/elksweb >> build/compiler-command.txt
printf '\n' >> build/compiler-command.txt
ia16-elf-gcc "${cflags[@]}" -Wl,-Map,build/elksweb.map "${objects[@]}" -o build/elksweb
python3 toolchain/stack-report.py build
file build/elksweb
sha256sum build/elksweb
objdump86 build/elksweb > build/elksweb.header.txt
disasm build/elksweb > build/elksweb.dis
ia16-elf-objdump -d -z --insn-width=16 -M intel,i8086 build/elksweb.elf > build/elksweb.elf.dis
ia16-elf-readelf -W -s build/elksweb.elf > build/elksweb.symbols.txt
ia16-elf-gcc --version > build/compiler-version.txt
python3 toolchain/isa-audit.py build/elksweb build/elksweb.elf build/elksweb.elf.dis --map build/elksweb.map --output build/isa-audit.json
printf 'ELKSWEB_APP_BUILD_OK\n'
