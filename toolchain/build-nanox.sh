#!/bin/sh
# Build a separate medium-model Nano-X application for ELKS/PC-98.
set -eu
TOPDIR=${ELKSWEB_ELKS:-${TOPDIR:-}}
: "${TOPDIR:?Set TOPDIR or ELKSWEB_ELKS to a built ELKS checkout}"
: "${MWDIR:?Set MWDIR to the Microwindows source used for the Nano-X server}"
TOPDIR=$(cd "$TOPDIR" && pwd)
MWDIR=$(cd "$MWDIR" && pwd)
export TOPDIR
PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
export PATH
cd "${ELKSWEB_SOURCE:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
out=build/nanox
mkdir -p "$out"
cc=${CC:-ia16-elf-gcc}
# Nano-X's small-model GrClose stores a callback in a data pointer. Keep the
# actual function-pointer type when compiling its client for medium model.
sed 's/void \* oldSignalHandler = signal/void (*oldSignalHandler)(int) = signal/' \
    "$MWDIR/src/nanox/client.c" > "$out/client.c"
set --
for source in src/*.c image/*.c font/*.c platform/elks_nanox.c \
        "$out/client.c" "$MWDIR"/src/nanox/nxproto.c \
        "$MWDIR"/src/nanox/nxutil.c "$MWDIR"/src/drivers/osdep.c; do
    object="$out/$(basename "${source%.c}").o"
    "$cc" -march=i8086 -mtune=i8086 -mcmodel=medium -melks-libc -Os \
        -ffunction-sections -fdata-sections -fno-builtin-printf -fno-builtin-fprintf \
        -DELKSWEB_NANOX=1 -DCONFIG_ARCH_PC98=1 \
        -DELKS=1 -DUNIX=1 -DNDEBUG=1 -DNONETWORK=0 \
        '-DMWCONFIG_FILE="mwconfig.elks"' -DMWPIXEL_FORMAT=MWPF_PALETTE \
        -DSCREEN_PIXTYPE=MWPF_PALETTE \
        -I./src -I./platform -I./font -I"$MWDIR/src/include" -I"$MWDIR/src/elksdrivers" -I"$MWDIR/src/nanox" \
        -c "$source" -o "$object"
    set -- "$@" "$object"
done
"$cc" -march=i8086 -mtune=i8086 -mcmodel=medium -melks-libc \
    -Wl,--gc-sections,-Map,"$out/elksweb.map" "$@" -o "$out/elksnx"
assets="$out/lib/webnx"
mkdir -p "$assets"
cp share/nanox/welcome.htm share/nanox/color.htm share/nanox/webnx.gif "$assets/"
cp share/chart.gif "$assets/"
printf '%s\n' "WebNX runtime built: $out/elksnx"
