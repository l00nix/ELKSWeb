#!/bin/sh
# Host checks against the actual Nano-X headers used for the native client.
set -eu
: "${MWDIR:?Set MWDIR to the Microwindows source used for the Nano-X server}"
MWDIR=$(cd "$MWDIR" && pwd)
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
out=build/nanox-tests
mkdir -p "$out"
cc=${HOST_CC:-cc}
case $(uname -s) in
    Darwin) discard=-Wl,-dead_strip ;;
    *) discard=-Wl,--gc-sections ;;
esac
for test in nanox_events_test nanox_text_test; do
    "$cc" -O1 -g -Wall -Wextra -DELKSWEB_NANOX=1 \
        -ffunction-sections -fdata-sections \
        -I"$MWDIR/src/include" -Iplatform -Ifont \
        "platform/tests/$test.c" platform/elks_nanox.c font/font.c \
        "$discard" -o "$out/$test"
    "$out/$test"
done
