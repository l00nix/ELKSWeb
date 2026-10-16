# Building and running

The application uses ELKS's IA16 GCC toolchain, not the host C compiler or a DOS C++ toolchain. The pinned candidate was built with ia16-elf-gcc 6.3.0 and exercised on ELKS 0.9.2-dev. These instructions have not yet been validated as a fresh-machine bootstrap; a self-contained reproducible release recipe remains a beta prerequisite.

## Native application

On a Linux build host, prepare an isolated ELKS checkout and build its toolchain, libc and host tools following the [upstream ELKS instructions](https://github.com/ghaerr/elks). The scripts require bash, Python 3, sha256sum, and the ELKS tools `elf2elks`, `objdump86` and `disasm`, in addition to IA16 GCC/binutils.

The recorded build tree was based on ELKS commit `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`. Its generic configuration enabled `CONFIG_CONSOLE_DIRECT`, `CONFIG_KEYBOARD_SCANCODE`, `CONFIG_CHAR_DEV_MEM`, `CONFIG_INET` and `CONFIG_ETH_NE2K`. Direct-console graphics/raw-keyboard ioctls must be available; a serial-only kernel is insufficient. These options identify prerequisites, not a complete reproducible kernel configuration. The exact final kernel config still needs to be captured for a release.

From this repository root:

```sh
export ELKSWEB_ELKS=/absolute/path/to/isolated/elks
export ELKSWEB_SOURCE="$PWD"
bash toolchain/build-app.sh
```

The script targets `-march=i8086 -mtune=i8086 -mcmodel=small -melks-libc`. Outputs go to `build/`, including the executable, retained ELF, linker map, compiler identity, disassembly, stack report and static ISA audit. The ISA audit is not a substitute for runtime testing.

Copy `build/elksweb` into `/bin/elksweb` on a suitable ELKS test installation and `share/welcome.htm` into `/root/welcome.htm`. Start ELKS networking using its documented configuration before loading HTTP pages. The browser needs a writable `/tmp` and a graphics-capable controlling console.

## Optional test image

`toolchain/package-image.sh` modifies the specified ELKS checkout's root filesystem template and creates a 2.88 MB FAT test disk. It installs browser autostart and disables unrelated network daemons in that template. Use a dedicated disposable ELKS checkout, not a production installation or an unrelated work tree. ELKS kernel/root filesystem/image prerequisites must already be built.

```sh
bash toolchain/package-image.sh
bash toolchain/run-qemu.sh http://68k.news/
```

The QEMU launcher needs `qemu-system-i386` and mtools `mcopy`. It boots a disposable image copy with a 486 CPU for ELKS integration testing. It does not emulate an 8088. Downloads in that session disappear when the temporary image is removed.

## 86Box 8088 configuration

The demonstrated setup uses 86Box 4.2.1 build 6130, IBM XT (1986), Intel 8088 at 4.772728 MHz, 640 KB RAM, CGA, a Monster FDC with Multi-Floppy BIOS 2.7, and a 2.88 MB drive A. BIOS setup selects type 6 for logical/physical drive 0, disables other drives, and uses the Floppy BIOS IPL. Obtain required ROMs separately; none are bundled.

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

Host tests do not validate 16-bit ABI, far pointers or 8088 timing. For actual-reference comparison, see [tests/README.md](../tests/README.md). Supply a separately obtained MicroWeb reference image explicitly; it is not bundled.

Optional font and image checks:

```sh
python3 -m unittest discover -s font -p 'test_*.py'
python3 image/tests/test_gif.py
python3 image/tests/test_dimensions.py
```

The image scripts require Pillow in the selected Python environment. The font tests require the host C compiler but no Pillow.
