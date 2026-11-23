#!/bin/sh
# Stage one set of pages for both browsers. Existing launch paths stay usable.
set -eu
: "${1:?Usage: stage-web-data.sh DESTINATION_ROOT}"
base=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
dest=$1
mkdir -p "$dest/lib/web" "$dest/lib/elksweb" "$dest/lib/webnx" "$dest/lib/elksnx"
cp "$base/share/welcome.htm" "$dest/lib/web/welcome.htm"
cp "$base/share/color.htm" "$dest/lib/web/color.htm"
cp "$base/share/elksweb.gif" "$base/share/elkswebc.gif" "$base/share/chart.gif" \
   "$base/share/nanox/webnx.gif" "$dest/lib/web/"
# These are byte-identical compatibility copies, not separate welcome sources.
# Absolute asset/link paths keep pages usable from the former directories.
for file in lib/web/welcnx.htm lib/web/start.htm lib/web/startnx.htm \
            lib/elksweb/welcome.htm lib/webnx/welcome.htm lib/elksnx/welcome.htm; do
    cp "$base/share/welcome.htm" "$dest/$file"
done
for file in lib/web/colornx.htm lib/elksweb/color.htm lib/webnx/color.htm; do
    cp "$base/share/color.htm" "$dest/$file"
done
