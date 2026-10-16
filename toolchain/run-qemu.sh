#!/usr/bin/env bash
# Open an isolated copy of the native ELKS image. Never writes a physical disk.
set -euo pipefail
script_dir=$(cd "$(dirname "$0")" && pwd)
app_dir=$(cd "$script_dir/.." && pwd)
qemu=${ELKSWEB_QEMU:-qemu-system-i386}
disk=${ELKSWEB_IMAGE:-$app_dir/build/elksweb.img}
url=${1:-/root/welcome.htm}
if [[ $# -gt 1 ]]; then
    printf 'Usage: %s [http://address/ or guest-file-path]\n' "$0" >&2
    exit 2
fi
command -v "$qemu" >/dev/null
command -v mcopy >/dev/null
test -f "$disk"
session_dir=$(mktemp -d "${TMPDIR:-/tmp}/elksweb-qemu.XXXXXX")
trap 'rm -rf "$session_dir"' EXIT
cp "$disk" "$session_dir/session.img"
printf '%s\n' "$url" > "$session_dir/qaurl"
printf '%s\n' "${HTTP_PROXY:-}" > "$session_dir/qaproxy"
mcopy -o -i "$session_dir/session.img" "$session_dir/qaurl" ::/root/qaurl
mcopy -o -i "$session_dir/session.img" "$session_dir/qaproxy" ::/root/qaproxy
"$qemu" -machine isapc -cpu 486 -m 8M \
    -accel tcg,one-insn-per-tb=on -vga std \
    -drive "file=$session_dir/session.img,if=floppy,format=raw,snapshot=on" \
    -boot a -netdev user,id=net0 \
    -device ne2k_isa,netdev=net0,irq=3,iobase=0x300 \
    -monitor none -serial none
