#!/usr/bin/env bash
# Build a host-editable FAT test image. Never operates on a physical disk.
set -euo pipefail
: "${ELKSWEB_ELKS:?Set ELKSWEB_ELKS to an isolated, built ELKS checkout}"
export TOPDIR="$ELKSWEB_ELKS"
export PATH="$TOPDIR/elks/tools/bin:$TOPDIR/cross/bin:$PATH"
app_root=${ELKSWEB_SOURCE:-$(cd "$(dirname "$0")/.." && pwd)}
template="$TOPDIR/elkscmd/rootfs_template"
case "${ELKSWEB_TEST_FIXTURES:-0}" in 0|1) ;; *)
    echo 'ELKSWEB_TEST_FIXTURES must be 0 or 1' >&2; exit 2 ;;
esac
install "$app_root/build/elksweb" "$template/bin/elksweb"
mkdir -p "$template/root"
install -m 644 "$app_root/share/welcome.htm" "$template/root/welcome.htm"
install -m 644 "$app_root/share/elksweb.gif" "$template/root/elksweb.gif"
install -m 644 "$app_root/share/logo-source.txt" "$template/root/logo-src.txt"
# Default image is the normal runtime. Fixtures are an explicit test-image option.
# Remove only paths previously owned by this packager in its isolated template.
rm -rf "$template/root/frog"
rm -f "$template/root/test.htm" "$template/bin/webfrog" "$template/bin/webnews" \
      "$template/root/webfrog" "$template/root/webnews"
if test "${ELKSWEB_TEST_FIXTURES:-0}" = 1; then
    mkdir -p "$template/root/frog"
    for fixture in index.htm http.htm results.htm article.htm images.htm frog.gif README.txt COPYING.txt; do
        install -m 644 "$app_root/tests/fixtures/frogfind/$fixture" "$template/root/frog/$fixture"
    done
    install -m 644 "$app_root/tests/fixtures/frogfind/PROVENANCE.json" "$template/root/frog/source.txt"
    install -m 644 "$app_root/tests/fixtures/local.htm" "$template/root/test.htm"
fi
# Browser appliance needs the TCP client daemon, not FTP/telnet server processes.
# Only this isolated rootfs template is changed; preserve upstream project images.
sed -i 's/^netstart=.*/netstart=""/' "$template/etc/net.cfg"
printf '%s\n' "${ELKSWEB_URL:-/root/welcome.htm}" > "$template/root/qaurl"
printf '%s\n' "${ELKSWEB_PROXY:-}" > "$template/root/qaproxy"
printf '%s\n' "${ELKSWEB_VIDEO:-}" > "$template/root/qavideo"
# Drop any previous browser startup block before appending it again.
sed -i '/^# ELKSWEB_AUTORUN/,$d' "$template/etc/rc.sys"
cat >> "$template/etc/rc.sys" <<'RC'
# ELKSWEB_AUTORUN
HTTP_PROXY=`cat /root/qaproxy`
if test "$HTTP_PROXY" != ""; then export HTTP_PROXY; else unset HTTP_PROXY; fi
url=`cat /root/qaurl`
video=`cat /root/qavideo`
if test "$video" != ""; then exec /bin/elksweb -video "$video" "$url"; fi
exec /bin/elksweb "$url"
RC
cat > "$template/bootopts" <<'BOOT'
## ELKSWeb generic IBM PC test image
net=ne0
ne0=3,0x300
buf=16
BOOT
# Early loader reads a complete cluster and requires zero padding.
truncate -s 1024 "$template/bootopts"
# Preserve the established system defaults while selecting a FAT test disk.
cp "$TOPDIR/.config" "$TOPDIR/image/elksweb.config"
sed -i -e 's/^CONFIG_IMG_MINIX=y/# CONFIG_IMG_MINIX is not set/' \
    -e 's/^# CONFIG_IMG_FAT is not set/CONFIG_IMG_FAT=y/' \
    -e 's/^CONFIG_IMG_FD1440=y/# CONFIG_IMG_FD1440 is not set/' \
    -e 's/^# CONFIG_IMG_FD2880 is not set/CONFIG_IMG_FD2880=y/' \
    "$TOPDIR/image/elksweb.config"
make -C "$TOPDIR/image" -f Make.image CONFIG="$TOPDIR/image/elksweb.config" DESTDIR="$TOPDIR/target" NAME=elksweb
cp "$TOPDIR/image/elksweb.img" "$app_root/build/elksweb.img"
sha256sum "$app_root/build/elksweb.img"
