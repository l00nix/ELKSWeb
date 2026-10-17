# Install ELKSWeb 0.1 from a release

No compiler is required. These instructions install the browser on an existing compatible ELKS system; they do not replace its operating system or format a disk. ELKSWeb is a native ELKS executable, not a DOS, Windows, macOS or modern Linux application.

You need a graphics-capable ELKS console, a writable `/tmp`, and CGA, supported EGA or VGA hardware. HTTP browsing also needs working ELKS networking/`ktcp`; the local welcome page works offline. All display modes are monochrome in 0.1.

## 1. Download on a modern computer

Open [ELKSWeb releases](https://github.com/l00nix/ELKSWeb/releases), select 0.1 and expand **Assets**. GitHub requires HTTPS, so use a modern computer to download, then transfer the files to ELKS. While the repository and release draft remain private, only authorized GitHub accounts can access them.

| Download | Use |
| --- | --- |
| `ELKSWeb-0.1-runtime.tar.gz` and matching `.sha256` | Recommended first installation: compiled binary, welcome HTML, GIF logo and notices |
| `elksweb-0.1` and matching `.sha256` | Standalone compiled binary, useful for an existing installation |
| `ELKSWeb-0.1-source.tar.gz` | Corresponding source, for rebuilding or redistribution; not needed to run the browser |
| `ELKSWeb-0.1-test-image.tar.gz` | Optional generic ELKS/QEMU test environment; not an HP installer |

GitHub's automatically generated **Source code** archives are not the compiled runtime package. Keep the supplied notices; offer the corresponding source alongside redistributed executable copies.

## 2. Verify and extract on the modern computer

Download both the chosen file and its matching `.sha256` into the same directory. In that directory, on Linux:

```sh
sha256sum -c ELKSWeb-0.1-runtime.tar.gz.sha256
tar -xzf ELKSWeb-0.1-runtime.tar.gz
```

On macOS, use `shasum -a 256 -c ELKSWeb-0.1-runtime.tar.gz.sha256` for the checksum, then the same `tar` command. Continue only if verification reports success.

On Windows PowerShell:

```powershell
Get-FileHash .\ELKSWeb-0.1-runtime.tar.gz -Algorithm SHA256
Get-Content .\ELKSWeb-0.1-runtime.tar.gz.sha256
tar -xzf .\ELKSWeb-0.1-runtime.tar.gz
```

Compare the displayed hashes; letter case does not matter. If your Windows installation has no `tar`, use an archive utility that handles `.tar.gz` files. For the standalone binary, substitute `elksweb-0.1` and `elksweb-0.1.sha256` in the checksum commands; no extraction is needed.

The runtime archive extracts into `ELKSWeb-0.1-runtime/`. You can also verify its individual files on the host by entering that directory and running `sha256sum -c SHA256SUMS` (Linux) or `shasum -a 256 -c SHA256SUMS` (macOS). ELKS itself does not need these host verification tools.

## 3. Transfer to the ELKS filesystem

Use your existing binary-safe serial/file-transfer method, configured network transfer or mounted ELKS disk. Preserve the binary and GIF bytes exactly; do not paste them into a terminal or use a text-mode transfer. Copy the extracted files according to this table:

| File inside `ELKSWeb-0.1-runtime/` | Destination on ELKS |
| --- | --- |
| `bin/elksweb` | `/root/ew-new` (temporary staging name) |
| `share/welcome.htm` | `/root/welcome.htm` |
| `share/elksweb.gif` | `/root/elksweb.gif` |
| `share/logo-source.txt` | `/root/logo-src.txt` |

Retain the entire downloaded package and its notices with the installation. If storing the notices on ELKS, create `/root/ewdocs` with `mkdir /root/ewdocs` and copy `COPYING`, `font/COPYING`, `licenses/ELKS-LICENSE.txt` and `licenses/ELKS-libc-notices.txt` there under distinct short names such as `COPYING`, `FONT.txt`, `ELKS.txt` and `LIBC.txt`. Keep the source archive available for redistribution.

For a standalone-binary upgrade, transfer the downloaded `elksweb-0.1` to `/root/ew-new`; existing welcome files can remain in place. A binary-only first installation will not include the default welcome page: use the runtime package for that page, or launch with an explicit local file or HTTP URL.

## 4. Install and start on ELKS

Exit any running ELKSWeb instance. If upgrading, first save the old executable with `cp /bin/elksweb /bin/ew-old`. Then, as root, install the staged file:

```sh
cp /root/ew-new /bin/elksweb
chmod 755 /bin/elksweb
elksweb --version
```

Check that the version reports **0.1**, then run from the machine's graphics console:

```sh
elksweb
```

Choose one of the detected display modes and press Enter. The welcome page at `/root/welcome.htm` should open, with its GIF logo and keyboard help. Only supported modes are offered; a CGA-only machine showing just CGA is expected. Press Escape to exit.

On the tested HP 200LX ELKS 3.8 beta 1 setup, enable translated keyboard input in the same shell before launch:

```sh
export ELKSWEB_COOKED_KEYS=1
elksweb -video cga /root/welcome.htm
```

The browser displays on the palmtop or emulator screen. A serial terminal is useful for transferring files and console administration, but is not the graphical browser display.

## 5. Try a page

After configuring the ELKS native network stack, try:

```sh
elksweb http://68k.news/
elksweb http://frogfind.8088retro.com/
```

Use F6 or Ctrl-L to edit the address, Tab and Enter to follow links, Page Up/Page Down to scroll, and Backspace to go back. A local file can be opened with `elksweb /root/example.htm`. Neither offline website fixtures nor the project's `webfrog`/`webnews` launchers are required.

## If something does not work

- **Permission denied:** check that `/bin/elksweb` has executable permissions (`chmod 755 /bin/elksweb`).
- **Cannot execute:** confirm this is a compatible ELKS installation, the binary transfer was byte-preserving, and you downloaded the executable rather than a GitHub HTML page or source archive.
- **Welcome page or logo missing:** check `/root/welcome.htm` and `/root/elksweb.gif`. Those files are in the runtime package, not in the standalone binary.
- **Local pages work but websites do not:** check ELKS networking, DNS and `ktcp`; use an `http://` URL. Native HTTPS is not supported.
- **Only CGA appears:** the selector only lists detected supported modes. EGA requires a supported colour adapter and at least 128 KB video RAM.
- **Exit does not return normally:** an unresolved cold-boot 86Box exit anomaly is recorded in [8088 validation](8088-VALIDATION.md). The subsequent normal-shell repeat passed, but the original cause is not established. Include your ELKS build, emulator/machine, display mode and startup steps when reporting it.

Page loading can be slow on early hardware. See [release notes](RELEASE-0.1.md) for fixed document limits, unsupported features and the full validation scope.
