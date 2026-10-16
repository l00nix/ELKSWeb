# Clean-build validation 001

On 2026-10-16, ELKSWeb commit `4fa4907bff0a5a11d82ec26ce503a255e5d9bf74` was built and packaged against a fresh checkout of ELKS `89d09706f17c123f9e0f5ef7cba2eb6745e8478c`. Binutils, GCC, its prerequisite libraries, emu86, ELKS libc, kernel, userspace and image tools were compiled during this run. No generated tools, libraries, kernel, root filesystem or images from the established builder were reused.

The disposable Ubuntu 22.04 container had three CPUs and 5 GiB RAM assigned. Its only bind mount was the new work directory. The base image was `ubuntu@sha256:5ec03bb3441e8b0bf3b4f9cd4629a1ae763010dc3035bb8da3ae6cf026486401`. The complete package list, command logs, source revisions and checksums are retained in the private validation evidence. The compiler was IA16 GCC 6.3.0, built from the commit pinned by ELKS. Both compiler and libc paths resolved inside the new checkout.

The browser was transferred as a Git bundle because the build host did not need repository credentials. Its final bundle SHA256 was `8886646f10d96d0001907f6aa2da42225d1d59c00154607142eae223ee034097`. An earlier bundle was checked out initially, then replaced with the final commit before any browser compilation. The retained final source archive SHA256 is `49fd1bdbb9d7b4ed979cf575149f5fc434c9c6990c1c86eff54165f84f77e6ba`.

## Recipe correction and source integrity

The first system build exposed a missing host dependency: `xxd`, used to generate the MBR include. Installing it alone was insufficient because the failed command had left an empty `mbr_autogen.c` beside an existing `mbr.bin`. Those two generated outputs were removed and regenerated in the same clean tree. The corrected [build recipe](BUILDING.md) installs `xxd` before compilation. No ELKS source patch was needed.

A later metadata collection command hit Git's ownership check after the container's exit handler returned files to the host user. A command-local `safe.directory` exception for the known checkout fixed collection; it did not alter the build inputs. Initial failures and successful resumed stages are retained separately.

Before browser packaging, ELKS `git status` and `git diff` were empty. The input and resulting `.config` were byte-identical. The browser working tree remained clean after compilation. The only subsequent tracked ELKS changes were the intended root-template `bootopts`, `net.cfg` and `rc.sys` changes made by the package script; the browser, welcome page and QA startup settings were added as documented.

## Clean artifacts

| Artifact | SHA256 |
|---|---|
| Interactive-default 2.88 MB image | `1e0e9e567fdb7ef782d20616be8517c39da89fbf80030acedad234e1a28d60a1` |
| ELKS browser executable | `0c2dad923fd4ad715d1e7a32721976af1b251abc33d334383e4ec77facd14d81` |
| Retained linked ELF | `c4e51db82912ef5e6dad08f8c9bfd4b9f9e14274559cd6a5fc33aba25f33df79` |
| Fresh ELKS kernel image | `4550fc18551e1d9582dc944083bace53b3dd469b771177f4c4b19b45e15d3ba6` |

The executable was extracted from the FAT image and verified byte-for-byte against the linked build output. Guest `/root/qavideo` contains only a newline, preserving the interactive display selector. The local handoff image is a byte-identical copy of the packaged image.

The browser build emitted no compiler warnings. Static ISA validation decoded all 64,064 executable bytes, covering 25,712 instructions with no forbidden opcodes or ambiguous/uncovered bytes. The code segment has 1,472 bytes remaining below 64 KiB. Initialized data is 12,128 bytes and BSS is 38,432 bytes. Including the default 4 KiB heap and 4 KiB stack, near allocation is 58,752 bytes, leaving 6,768 bytes before arguments/environment; the configured 1,024-byte reserve check passed. The largest reported individual compiler stack frame is 336 bytes, which does not establish total call-chain stack use.

## Downloaded source archives

All were downloaded during this run; the versions/commits came from the pinned ELKS `tools/Makefile`.

| Archive | SHA256 |
|---|---|
| binutils-ia16 `69e12ea2c125ff830580abbe4699d35ba002148b` | `2ff25649409f16d49ddaa9cd32b382cf10c1d5fc8ceb11d3cb05b5d28f16bc4a` |
| gcc-ia16 `ca893320926dc93552390b892a202e9373d040c0` | `b6e5e3a55caf59faa08b038177821ab84a33c7f8f921741aa92f1b4fbee19952` |
| emu86 `16dfcf0d68dccf9211a575c2a6ff90d5a192dd61` | `3473f089b9ced5f51b87ef2a200e30b91cc94ba2573f7e7cb9d2f95c64e1f666` |
| GMP 6.1.2 | `5275bb04f4863a13516b2f39392ac5e272f5e1bb8057b18aec1c9b79d73d8fb2` |
| MPFR 3.1.5 | `ca498c1c7a74dd37a576f353312d1e68d490978de4395fa28f1cbd46a364e658` |
| MPC 1.0.3 | `617decc6ea09889fb08ede330917a00b16809b8db88c29c31bfbb49cbf88ecc3` |

## Scope and evidence

This closes the source-bootstrap/build gate after the dependency correction. Native runtime QA is a separate result recorded with the beta checkpoint. Static decoding does not establish full 8088 execution. This run does not claim bit-identical whole-image reproduction: kernel build dates, FAT metadata and unpinned host package mirrors remain reproducibility limits. Speed and responsiveness are excluded from the first-beta decision.

Private evidence is retained under `qa/clean-build-001/`: the source archive and bundle, source-file hash manifest, original/resume scripts, image and executable, retained ELF/map/disassembly/stack report, ISA audit, full logs/configuration/package list, container identity, initial failure records and final artifact manifest. Evidence is intentionally outside the public source tree's tracked files.
