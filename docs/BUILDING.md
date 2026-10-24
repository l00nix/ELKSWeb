# Building the current 0.2 release

The lightweight external builder and audited developer builder remain separate.
Install the binary as `/bin/elksweb`; see [INSTALL.md](INSTALL.md) for assets under
`/lib/elksweb`. Source and runtime release archives are generated with
`toolchain/package-release-0.2.py --help`; the original `package-release.py` remains
pinned to 0.1 for historical reproducibility. The new packager requires the exact
source revision, audited binary hash and matching ELKS source archive. Packaging
is a host-side operation and adds no dependencies to the external builder.

The historical clean-build pins and 0.1 qualification records below retain their
original scope; they are not claims about a fresh 0.2 hardware test.

# Building and running

The application uses ELKS's IA16 GCC toolchain, not the host C compiler or a DOS C++ toolchain. Version 0.1 was built with ia16-elf-gcc 6.3.0 and exercised on ELKS 0.9.2-dev. The source bootstrap below was validated on 2026-10-16 in a new Ubuntu 22.04 container, including a freshly compiled toolchain, libc, kernel and image. See [the clean-build record](CLEAN-BUILD-001.md) for pins, hashes, the dependency correction and remaining reproducibility limits.

## Minimal build for upstream ELKS

For a prepared ELKS checkout with its IA16 toolchain, libc and host tools built:

```sh
ELKSWEB_ELKS=/absolute/path/to/elks sh toolchain/build-external.sh
```

This produces `build/elksweb` and a linker map. It compiles every source afresh
and needs only a POSIX shell, standard host utilities and the ELKS toolchain.
Python, `sha256sum`, OpenWatcom and the optional audit tools are not required.
The compiler flags retain the 8086 instruction target and small memory model.
Use the audited build below for release validation and stack/ISA reports.

The merged upstream integration provides `./buildext.sh elksweb` (also included
in `./buildext.sh all`). It checks out this repository in `extapps/ELKSWeb`,
passes the ELKS tree as `ELKSWEB_ELKS`, and runs this minimal build script.
The companion `elkscmd/ExtApplications` entries install the executable as
`/bin/elksweb`, welcome page and logo under `/root`, and notices under
`/lib/elksweb`. They select hard-disk images only, with no floppy-size tags.
Upstream clones the public repository. Its current asset mapping still uses the
legacy `/root` layout, supported by the 0.2 fallback. Moving those upstream entries
to `/lib/elksweb` is a separate follow-up; the standalone 0.2 runtime already uses
the new layout. No browser autostart, network configuration,
HP-specific keyboard setting or kernel change is part of this integration.

## Native application with developer audits

On a Linux build host, prepare an isolated ELKS checkout and build its toolchain, libc and host tools following the [upstream ELKS instructions](https://github.com/ghaerr/elks). The scripts require bash, Python 3, sha256sum, and the ELKS tools `elf2elks`, `objdump86` and `disasm`, in addition to IA16 GCC/binutils.

The recorded build tree was based on ELKS commit `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`. Its generic configuration enabled `CONFIG_CONSOLE_DIRECT`, `CONFIG_KEYBOARD_SCANCODE`, `CONFIG_CHAR_DEV_MEM`, `CONFIG_INET` and `CONFIG_ETH_NE2K`. Direct-console graphics/raw-keyboard ioctls must be available; a serial-only kernel is insufficient. The exact tested configuration is retained as [config/elks-generic.config](config/elks-generic.config). The clean validation used a verified checkout of that commit, with no upstream source changes before packaging; its configuration remained byte-identical during the system build. Packaging then applied the documented browser startup and filesystem changes.

## Clean-checkout validation procedure

Use a separate disposable Linux VM or container with its own filesystem, CPU allocation and output directory. Do not mount the established builder's ELKS checkout or `cross/` directory writable, or reuse its generated libc, headers, kernel, root template or disk images. A second directory on the same busy builder still competes for its CPU and disk. The following procedure was exercised by the clean-build validation, with the required `xxd` package added after the first attempt exposed its absence.

The pinned ELKS tree's `BUILD.md` and CI use Ubuntu 22.04 and require a host C/C++ build environment, Bash, Git, wget, Python 3, texinfo, ncurses development headers, libelf development headers, ncompress, bison, flex and SDL2 development headers. Also provide `file`, coreutils, tar, gzip, bzip2, mtools and xxd (used to generate bootblock headers); QEMU is needed only for subsequent runtime checks. On a disposable Ubuntu 22.04 host the corresponding package preparation is:

```sh
sudo apt-get update
sudo apt-get install build-essential git wget ca-certificates python3 file \
  texinfo libncurses5-dev libelf-dev ncompress bison flex libsdl2-dev \
  mtools bzip2 xxd
```

Record the host image digest or OS release and installed package versions. Host packages and downloaded archive checksums are not currently locked by this repository. The ELKS commit pins IA16 GCC source at `ca893320926dc93552390b892a202e9373d040c0`, binutils at `69e12ea2c125ff830580abbe4699d35ba002148b`, emu86 at `16dfcf0d68dccf9211a575c2a6ff90d5a192dd61`, and GMP/MPFR/MPC at 6.1.2/3.1.5/1.0.3. Its toolchain builder downloads these inputs; record SHA256 values of the resulting `cross/dist/` archives. No OpenWatcom or external ELKS applications are needed for this recipe.

First commit the intended ELKSWeb candidate and set `ELKSWEB_REV` to that full commit ID. The private repository must be readable by the validation host. A clone contains committed files only; current working-tree edits are not a clean-checkout input. If the build host cannot authenticate to the private repository, create a bundle with `git bundle create browser.bundle HEAD`, retain its SHA256, transfer it privately, and substitute that file for the browser clone URL below. Verify the checked-out commit with `git rev-parse HEAD`; the bundle must contain the intended commit. Run the following in Bash, keeping the fresh paths free of spaces because upstream ELKS make rules assume that:

```sh
set -euo pipefail
: "${ELKSWEB_REV:?Set the full committed ELKSWeb candidate revision}"
repro_root=$(mktemp -d /tmp/elksweb-repro.XXXXXX)
mkdir "$repro_root/logs"
git clone https://github.com/l00nix/ELKSWeb.git "$repro_root/browser"
git -C "$repro_root/browser" checkout --detach "$ELKSWEB_REV"
git clone https://github.com/ghaerr/elks.git "$repro_root/elks"
git -C "$repro_root/elks" checkout --detach 89d09706f17c123f9e0f5ef7cba2eb6745e8478c
(
  cd "$repro_root/elks"
  . ./env.sh
  export MAKEFLAGS=-j2 LC_ALL=C TZ=UTC
  mkdir -p cross
  make -C tools all > "$repro_root/logs/cross.log" 2>&1
  make defconfig > "$repro_root/logs/config.log" 2>&1
  cp "$repro_root/browser/docs/config/elks-generic.config" .config
  cp .config "$repro_root/logs/config.before"
  make all > "$repro_root/logs/system.log" 2>&1
  cp .config "$repro_root/logs/config.after"
)
export ELKSWEB_ELKS="$repro_root/elks"
export ELKSWEB_SOURCE="$repro_root/browser"
export LC_ALL=C TZ=UTC
cd "$ELKSWEB_SOURCE"
bash toolchain/build-app.sh > "$repro_root/logs/browser.log" 2>&1
bash toolchain/package-image.sh > "$repro_root/logs/image.log" 2>&1
```

`make defconfig` is intentional: it creates the generated keyboard configuration include needed by a pristine ELKS tree, before our saved configuration replaces its defaults. Copying `.config` then immediately running `make all` can otherwise fail on that missing include. If recovering from an earlier missing-`xxd` failure, run `make -C bootblocks clean` after installing it: that failure can leave an empty `mbr_autogen.c` beside an apparently current `mbr.bin`. Do not substitute upstream `build.sh auto`: it selects its own configurations and later builds other architectures. The toolchain and system stages above build and install ELKS libc and headers into this checkout's `cross/`, and produce the native `elf2elks`, `objdump86`, `disasm`, boot blocks and image prerequisites.

Review any configuration changes in `logs/config.after` against the saved input; retain both, the source revisions, logs, tool versions, archive checksums, browser executable/ELF hashes, map and ISA/memory reports. Verify that compiler and native-tool paths resolve inside the fresh checkout. Then boot the fresh image through the native display/history/form/image checks. A successful build alone is not a runtime pass. Repeat in a second empty workspace to assess byte equality of the browser executable.

Whole-image byte equality is an optional reproducibility check, not a first-beta release gate: the pinned ELKS kernel embeds the build date in `compiler-generated.h`, while FAT packaging preserves source file modification times and creates metadata. Setting `SOURCE_DATE_EPOCH` alone does not remove the kernel's explicit `date` command. A differing image hash therefore needs diagnosis, not an automatic claim of failure or reproducibility. The current release gate requires a demonstrated clean build and tested image; no byte-identical image claim is made.

## Building against an already prepared ELKS tree

From this repository root:

```sh
export ELKSWEB_ELKS=/absolute/path/to/isolated/elks
export ELKSWEB_SOURCE="$PWD"
bash toolchain/build-app.sh
```

The script targets `-march=i8086 -mtune=i8086 -mcmodel=small -melks-libc`. Outputs go to `build/`, including the executable, retained ELF, linker map, compiler identity, disassembly, stack report and static ISA audit. The ISA audit is not a substitute for runtime testing.

Install `build/elksweb` as executable `/bin/elksweb`, `share/welcome.htm` as `/lib/elksweb/welcome.htm`, and `share/elksweb.gif` as `/lib/elksweb/elksweb.gif` on a suitable ELKS installation. Retain the logo provenance from `share/logo-source.txt` as `/lib/elksweb/logo-src.txt`, and keep the supplied browser, font and ELKS/libc notices with redistributed packages. Running `elksweb` without a URL opens this local help page; website fixtures are not required. Start ELKS networking using its documented configuration before loading HTTP pages. The browser needs a writable `/tmp` and a graphics-capable controlling console. It opens a text-mode display selector by default. Press 1/2/3 and Enter, or Q and Enter to cancel. Available modes are genuine monochrome CGA 640×200, EGA 640×350 and VGA 640×480; EGA requires a color display and at least 128 KB video RAM. Detection rejects unavailable modes before changing the console. QEMU validation does not certify physical adapters.

For an explicit mode, including unattended tests:

```sh
elksweb -video cga /root/welcome.htm
elksweb -video ega http://68k.news/
elksweb -video vga -noimages http://frogfind.8088retro.com/
```

Full CLI: `elksweb [-video cga|ega|vga] [-invert] [-noimages] [http://URL or local-file]`. `--version` prints the version without entering graphics.

For the project's HP 200LX ELKS 3.8 beta 1 keyboard setup, set `ELKSWEB_COOKED_KEYS=1` before launching. The owner confirms the exact 0.1 executable runs on the standard HP and DS HP; this feedback is distinct from independently captured QEMU tests. See [release notes](RELEASE-0.1.md).

## Optional test image

`toolchain/package-image.sh` modifies the specified ELKS checkout's root filesystem template and creates a 2.88 MB FAT test disk. It installs browser autostart and disables unrelated network daemons in that template. Use a dedicated disposable ELKS checkout, not a production installation or an unrelated work tree. ELKS kernel/root filesystem/image prerequisites must already be built.

```sh
# Interactive default: help/logo installed, no website fixtures.
bash toolchain/package-image.sh
bash toolchain/run-qemu.sh http://68k.news/

# Optional fixture-enabled test image; still interactive by default.
ELKSWEB_TEST_FIXTURES=1 bash toolchain/package-image.sh
bash toolchain/run-qemu.sh /root/frog/index.htm

# Unattended fixture QA: bypass the selector with CGA.
ELKSWEB_TEST_FIXTURES=1 ELKSWEB_VIDEO=cga bash toolchain/package-image.sh
```

`ELKSWEB_TEST_FIXTURES` defaults to `0`; only `0` and `1` are accepted. Repackaging removes fixture/helper paths previously owned by this packager before optionally installing the test content. Neither `webfrog` nor `webnews` is part of the normal runtime. The default help page links to live sites and its own keyboard help, not to optional fixtures.

Packaging writes `${ELKSWEB_VIDEO:-}` to guest `/root/qavideo`. An empty value means the interactive selector; `cga`, `ega` or `vga` makes autostart pass the corresponding `-video` argument. The QEMU launcher uses that image setting; setting `ELKSWEB_VIDEO` only when launching QEMU does not alter an already packaged image.

The QEMU launcher needs `qemu-system-i386` and mtools `mcopy`. It boots a disposable image copy with a 486 CPU for ELKS integration testing. It does not emulate an 8088. Downloads in that session disappear when the temporary image is removed.

## Repeatable FrogFind fixtures

The live QA mirror is `http://frogfind.8088retro.com/`. The fixed fixtures are separate: copy the HTML and GIF files from `tests/fixtures/frogfind/` into guest `/root/frog`, then run `elksweb -video cga /root/frog/index.htm`. Opt in with `ELKSWEB_TEST_FIXTURES=1` when packaging a test image to install them under `/root/frog`; the default image omits them. Open the fixture path explicitly. The normal help page does not link to these optional files. The fixture QA harness also injects them into its disposable image. File-mode sample navigation works without PHP or networking; sample results are not live search results.

For a local HTTP fixture server on the QEMU host:

```sh
python3 -m http.server 18787 --bind 127.0.0.1 --directory tests/fixtures/frogfind
# In the guest:
elksweb -video cga http://10.0.2.2:18787/http.htm
```

See the fixture [instructions](../tests/fixtures/frogfind/README.txt), [provenance](../tests/fixtures/frogfind/PROVENANCE.json) and retained license. `mirror.htm` is the captured original homepage and is not an offline working search page.

## Separate distribution artifacts

`toolchain/package-release.py` assembles archives without building, publishing or changing repository visibility. Choose `--kind runtime`, `--kind source`, or `--kind test-image`. The runtime contains the approved executable, help HTML, original GIF logo and notices; offer the corresponding-source archive alongside it. The optional test-image archive includes the QEMU image, fixture resources and sources. No `webfrog`/`webnews` helpers are needed for normal installation.

The packager requires committed browser source, the pinned ELKS source archive and its SHA256, release notes, and a new output filename. Runtime/test-image packaging also checks the supplied executable, retained ELF and matching ISA report. It rejects compiled-source changes relative to the approved binary revision. For example, with the documented variables set:

```sh
: "${ELKSWEB_RELEASE_REV:?Set the full committed release revision}"
: "${ELKSWEB_ELKS_ARCHIVE:?Set the pinned ELKS Git archive path}"
: "${ELKSWEB_ELKS_ARCHIVE_SHA256:?Set its verified SHA256}"
python3 toolchain/package-release.py --kind runtime \
  --revision "$ELKSWEB_RELEASE_REV" --build-dir build \
  --elks-source "$ELKSWEB_ELKS_ARCHIVE" \
  --elks-source-sha256 "$ELKSWEB_ELKS_ARCHIVE_SHA256" \
  --notes docs/RELEASE-0.1.md --output ELKSWeb-0.1-runtime.tar.gz
```

For corresponding source, use `--kind source` and a distinct output filename; no `--build-dir` is required. For the optional image, use `--kind test-image`, a fixture-enabled image under the build directory, and `--image-sha256` with that exact validated image hash. Keep its `/root/qavideo` empty for interactive display selection. Run `--help` for all arguments. Verify each extracted artifact with its `SHA256SUMS` and retain `PACKAGE.json`; archive assembly and checksum verification do not replace runtime QA.

## 86Box 8088 configuration

Historical clean build005 passed CGA startup selection, local FrogFind GIF/link navigation, console restoration, live 68k.news rendering and Page Down in the following setup. Build004 separately exercised EGA and VGA; clean005 repeated all three modes in QEMU. Speed and responsiveness are excluded from this first-beta decision. The setup uses 86Box 4.2.1 build 6130, IBM XT (1986), Intel 8088 at 4.772728 MHz, 640 KB RAM, CGA, a Monster FDC with Multi-Floppy BIOS 2.7, and a 2.88 MB drive A. BIOS setup selects type 6 for logical/physical drive 0, disables other drives, and uses the Floppy BIOS IPL. Obtain required ROMs separately; none are bundled.

The exact 0.1 executable passes the QEMU checks documented in [QA-0.1.json](QA-0.1.json), including all three modes with the refreshed default help/logo. Its final Windows 86Box 8088 run remains pending; the build005 observations above do not substitute for it.

Network: NE2000 Compatible 8-bit, SLiRP, I/O 0x300, IRQ 3; disable conflicting serial ports. Guest address 10.0.2.15, gateway 10.0.2.2, mask 255.255.255.0. In a separate 86Box image copy, set:

```text
net=ne0
ne0=3,0x300,0,0x92
buf=16
```

The extra flags force byte transfers with 16 KB NIC RAM. The default QEMU packaging uses `ne0=3,0x300`; do not mistake that unmodified image for the tested 86Box configuration. Preserve bootopts cluster padding when editing the image.

## Host checks

With Python 3 and a host C compiler:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s platform/tests -p 'test_*.py'
```

The 0.1 full `tests/` run passed 288 tests using the bundled Python environment with Pillow available. Seven additional platform tests cover drawing, cursor restoration and bank-safe scrolling. The display tests include actual driver memory operations against simulated BIOS/console I/O, all three framebuffer layouts, clipped drawing/cursor restoration, unsupported adapters, menu cancellation and image geometry. Nine driver scenarios also passed ASan/UBSan.

Host tests do not validate 16-bit ABI, far pointers or 8088 timing. For actual-reference comparison, see [tests/README.md](../tests/README.md). Supply a separately obtained MicroWeb reference image explicitly; it is not bundled.

Optional font and image checks:

```sh
python3 -m unittest discover -s font -p 'test_*.py'
python3 image/tests/test_gif.py
python3 image/tests/test_dimensions.py
```

The image scripts require Pillow in the selected Python environment. The font tests require the host C compiler but no Pillow.
