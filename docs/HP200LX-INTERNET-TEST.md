# Live Internet test on the HP 200LX

ELKSWeb 0.1 successfully loaded and rendered the live HTTP homepages of [68k.news](http://68k.news/) and the [FrogFind mirror](http://frogfind.8088retro.com/) on a physical double-speed HP 200LX. The owner confirmed both results, and both pages were captured from the palmtop framebuffer. The photographs below show the actual machine.

## Test configuration

- Owner-identified double-speed HP 200LX; no clock-frequency measurement was made.
- Experimental local ELKS build, reporting `ELKS 0.9.2-dev hp200lx-3.8-beta2`, with its Minix root image on internal storage so the PCMCIA slot could hold the NIC.
- Accton EN2216 R02 PCMCIA Ethernet card, byte-wide NE2000-compatible access at I/O `0x300`, IRQ3.
- Native ELKS `ktcp`, static IPv4 configuration, LAN gateway/DNS and MTU 1000. Serial was used for administration and screen capture; website traffic used Ethernet.
- ELKSWeb 0.1, CGA 640×200 monochrome, with `ELKSWEB_COOKED_KEYS=1`.

## Observed results

| Check | Result |
| --- | --- |
| LAN connectivity | Four replies to four ping probes after interrupt routing was corrected |
| LAN HTTP transfer | 4,096-byte file downloaded; MD5 `2bcd3c4de20c918e19fab5c36249c70d` matched the served fixture |
| DNS | Both public hostnames resolved from ELKS |
| FrogFind mirror | HTTP 200; homepage, frog GIF and visible form controls rendered; reopening the page also succeeded |
| 68k.news | Approximately 92 KB downloaded; homepage eventually rendered after a long `Parsing...` stage |
| Physical confirmation | Owner observations, framebuffer captures and the two photographs below |

![68k.news on the physical HP 200LX](screenshots/hp200lx/68k-news-photo.png)

![FrogFind mirror on the physical HP 200LX](screenshots/hp200lx/frogfind-photo.png)

These photographs are rectangular crops of the owner-supplied originals. The retained pixels match the decoded originals exactly; there is no resizing, retouching or generated replacement screen content. Crop bounds and output checksums are recorded in [photo provenance](screenshots/hp200lx/provenance.json). Website text and artwork belong to their respective providers.

## Accton driver findings

The first blocker was initialization: this EN2216 R02 returned configuration-register values different from those required by the existing HP setup code, and its MAC address was at a different attribute-memory offset. Identity-specific handling was added after DOS-side diagnostics confirmed the card identity, MAC from NIC PROM, and byte-wide DMA operation.

With the card recognized, ELKS transmitted but received no packets. The HP GPIO24 pin used for PC Card RDY/IREQ was still routed to IRQ6 with its interrupt disabled, while the driver expected IRQ3. A documented live correction to active-low IRQ3 routing restored reception. The successful Internet tests used that correction.

A permanent kernel change has been built to establish the routing when the NIC opens and restore the saved routing when it closes. Host tests and linked-code checks passed, including preservation of other GPIO pins, the index selector and interrupt flags. Installation and a fresh hardware boot of that new kernel remain pending. The published ELKSWeb runtime and stock ELKS kernel must not be assumed to include these HP-specific fixes.

## Browser findings and remaining work

The lengthy blank `Parsing...` screen on 68k.news initially looked like a stall, but the page eventually rendered. The source cache already held about 92 KB before layout completed. This points to parsing/layout as a performance investigation area; no exact load time or CPU-versus-disk breakdown was measured.

The tested ELKS `urlget` also timed out for `68k.news`: its libc hostname helper treats names beginning with a digit as numeric addresses. ELKSWeb already uses explicit DNS resolution for digit-leading names that are not valid IPv4 literals, so the browser reached the site. This utility result should not be mistaken for a website or NIC failure.

These tests confirm live HTTP homepage loading and rendering, including a GIF. They do not yet establish link navigation, search submission, article reading, downloads through the browser UI, long-session stability or performance targets on this physical setup. The broader QEMU feature tests remain separate evidence. Native HTTPS, CSS and JavaScript remain unsupported.

Testing on the owner's Amstrad PPC 512 is planned in the coming days. No result for that machine is claimed yet. This documentation and photo update does not change the released browser executable or release archives.
