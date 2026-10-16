#!/usr/bin/env python3
"""Assemble a private archive from supplied artifacts; never builds or publishes.

Identical inputs produce identical archive bytes with the same Python/zlib.
The image itself is preserved, including its existing FAT timestamps.
"""
import argparse
import gzip
import hashlib
import io
import json
import pathlib
import re
import subprocess
import tarfile
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True, help='Full committed browser source SHA')
    parser.add_argument('--build-dir', required=True, type=pathlib.Path,
                        help='Contains elksweb, elksweb.elf, elksweb.img, isa-audit.json')
    parser.add_argument('--image-sha256', required=True, help='Expected validated image SHA256')
    parser.add_argument('--elks-source', required=True, type=pathlib.Path,
                        help='ELKS git archive, tar or tar.gz, with Git commit PAX header')
    parser.add_argument('--elks-revision', default='89d09706f17c123f9e0f5ef7cba2eb6745e8478c')
    parser.add_argument('--notes', required=True, type=pathlib.Path,
                        help='Release notes; drafts remain drafts in the archive')
    parser.add_argument('--output', required=True, type=pathlib.Path, help='New .tar.gz path')
    parser.add_argument('--version', default='0.1')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parent.parent
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.version):
        parser.error('Invalid version')
    for value in (args.revision, args.elks_revision):
        if not re.fullmatch(r'[0-9a-f]{40}', value):
            parser.error('Source revisions must be full lowercase Git commit IDs')
    if git(repo, 'rev-parse', args.revision + '^{commit}').decode().strip() != args.revision:
        parser.error('Browser revision did not resolve exactly')
    sidecar = args.output.with_name(args.output.name + '.sha256')
    if args.output.exists() or sidecar.exists():
        parser.error('Output or checksum sidecar exists; choose a new path')
    if not args.output.parent.is_dir():
        parser.error('Output parent directory must already exist')

    source_tar = git(repo, 'archive', '--format=tar', args.revision)
    with tarfile.open(fileobj=io.BytesIO(source_tar)) as archive:
        source = {m.name: archive.extractfile(m).read()
                  for m in archive.getmembers() if m.isfile()}
    epoch = int(git(repo, 'show', '-s', '--format=%ct', args.revision))
    elks_input = args.elks_source.read_bytes()
    elks_tar = gzip.decompress(elks_input) if elks_input[:2] == b'\x1f\x8b' else elks_input
    with tarfile.open(fileobj=io.BytesIO(elks_tar), mode='r:') as archive:
        if archive.pax_headers.get('comment') != args.elks_revision:
            parser.error('ELKS archive Git commit header does not match --elks-revision')
        licenses = [m for m in archive.getmembers()
                    if m.isfile() and m.name.rstrip('/').split('/')[-1] == 'LICENSE'
                    ]
        if licenses:
            depth = min(len(pathlib.PurePosixPath(m.name).parts) for m in licenses)
            licenses = [m for m in licenses if len(pathlib.PurePosixPath(m.name).parts) == depth]
        if len(licenses) != 1:
            parser.error('Expected one top-level ELKS LICENSE in source archive')
        elks_license = archive.extractfile(licenses[0]).read()

    build = args.build_dir
    binary = (build / 'elksweb').read_bytes()
    elf = (build / 'elksweb.elf').read_bytes()
    image = (build / 'elksweb.img').read_bytes()
    audit_bytes = (build / 'isa-audit.json').read_bytes()
    audit = json.loads(audit_bytes)
    if len(image) != 2880 * 1024 or digest(image) != args.image_sha256:
        parser.error('Image must be the expected 2.88 MB artifact')
    if (not audit.get('isa_static_pass') or not audit.get('memory', {}).get('memory_gate_pass')
            or audit.get('executable_sha256') != digest(binary)
            or audit.get('elf_sha256') != digest(elf)):
        parser.error('ISA/memory report must pass and match the supplied executable/ELF')
    with tempfile.TemporaryDirectory(prefix='elksweb-package-check-') as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / 'image.img').write_bytes(image)
        for guest, name in [('::/bin/elksweb', 'binary'), ('::/root/qavideo', 'video'),
                            ('::/root/welcome.htm', 'welcome')]:
            subprocess.run(['mcopy', '-i', str(tmp / 'image.img'),
                            guest, str(tmp / name)], check=True)
        if (tmp / 'binary').read_bytes() != binary:
            parser.error('Image contains a different browser executable')
        if (tmp / 'welcome').read_bytes() != source['share/welcome.htm']:
            parser.error('Image welcome page does not match the source revision')
        if (tmp / 'video').read_bytes().rstrip(b'\n'):
            parser.error('Release image must retain the interactive display selector')

    files = {
        'build/elksweb': binary,
        'build/elksweb.img': image,
        'source/ELKSWeb-source.tar.gz': gzip.compress(source_tar, mtime=0),
        'source/ELKS-source.tar.gz': gzip.compress(elks_tar, mtime=0),
        'licenses/ELKS-LICENSE.txt': elks_license,
        'RELEASE-NOTES.md': args.notes.read_bytes(),
        'validation/isa-audit.json': audit_bytes,
    }
    for name in ['COPYING', 'font/COPYING', 'font/provenance.json',
                 'toolchain/run-qemu.sh', 'docs/BUILDING.md',
                 'docs/config/elks-generic.config', 'share/welcome.htm']:
        files[name] = source[name]
    # These attributed sample pages have fixed local navigation, not live search.
    # Do not add captured news HTML/headlines to this list without provenance.
    for name in ['index.htm', 'http.htm', 'results.htm', 'article.htm', 'images.htm',
                 'frog.gif', 'mirror.htm', 'COPYING.txt', 'PROVENANCE.json', 'README.txt']:
        files['fixtures/frogfind/' + name] = source['tests/fixtures/frogfind/' + name]
    for name in ['compiler-command.txt', 'compiler-version.txt']:
        files['validation/' + name] = (build / name).read_bytes()
    files['README.txt'] = f'''ELKSWeb {args.version} — PRIVATE package

Read RELEASE-NOTES.md for this candidate's validation status and limitations.
No publication or hardware certification is implied by this archive.

ELKS installation: copy build/elksweb to /bin/elksweb on a compatible ELKS
system with a graphics console, working networking and writable /tmp.
Also copy share/welcome.htm to /root/welcome.htm for the default start page.
Run elksweb to choose CGA, EGA or VGA; Escape exits the browser.

HP 200LX with the project's ELKS 3.8beta1 setup: use its cooked-keyboard mode:
  export ELKSWEB_COOKED_KEYS=1
  elksweb -video cga /root/welcome.htm
This launch approach was exercised previously; physical 0.1 retesting remains
pending. Use the executable on the existing HP ELKS installation. The generic
2.88 MB image below is an emulator test image.

QEMU: install qemu-system-i386 and mtools, then run from this directory:
  bash toolchain/run-qemu.sh
  bash toolchain/run-qemu.sh http://68k.news/
The launcher uses a disposable disk copy and a 486 CPU; it does not emulate
an 8088. Files saved in that session disappear when the launcher exits.
The packaged image is unchanged and keeps its interactive display selector.

Offline samples: fixtures/frogfind contains fixed pages and an attributed
GIF. The 0.1 image already configures them under /root/frog; select the local
FrogFind link on its welcome page. For an existing ELKS installation, see the
fixture README.txt for copying them into /root/frog.
Do not treat sample results as live search. Captured news pages are omitted;
68k.news remains a live network example. Original/news-like test fixtures may
be added separately when their provenance is explicit.

Source: extract source/ELKSWeb-source.tar.gz and source/ELKS-source.tar.gz.
The complete ELKS source includes component-specific license notices; its
kernel and userspace components do not all have the same license.
Browser COPYING, font/COPYING and FrogFind COPYING.txt retain their notices.
The browser source archive also retains the repository's credited evidence
screenshots and documentation; website content belongs to its providers.

Verify extracted payloads with: sha256sum -c SHA256SUMS
The outer .sha256 file checks the archive itself. Hashes identify contents;
they are not a signature or a claim that runtime validation passed.
'''.encode()
    files['PACKAGE.json'] = (json.dumps({
        'version': args.version, 'visibility': 'private',
        'browser_revision': args.revision, 'elks_revision': args.elks_revision,
        'source_date_epoch': epoch, 'binary_sha256': digest(binary),
        'image_sha256': digest(image), 'elks_source_input_sha256': digest(elks_input),
        'runtime_validation': 'Not inferred by assembler; see supplied release notes.',
        'source_association': 'Source revisions declared by packager; artifact hashes and embedded executable checked.',
        'archive_reproducibility': 'Identical supplied inputs and Python/zlib yield identical archive bytes; no whole-image reproducibility claim.'
    }, indent=2, sort_keys=True) + '\n').encode()
    files['SHA256SUMS'] = ''.join(f'{digest(data)}  {name}\n'
                                for name, data in sorted(files.items())).encode()
    prefix = 'ELKSWeb-' + args.version + '-private/'
    # Prepare everything before creating the destination. No shell, network,
    # compiler, image write, tag, push or release API is invoked.
    with args.output.open('xb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for name, data in sorted(files.items()):
                    member = tarfile.TarInfo(prefix + name)
                    member.size, member.mtime = len(data), epoch
                    member.mode = 0o755 if name in ('build/elksweb', 'toolchain/run-qemu.sh') else 0o644
                    member.uid = member.gid = 0
                    member.uname = member.gname = ''
                    archive.addfile(member, io.BytesIO(data))
    archive_sha = digest(args.output.read_bytes())
    with sidecar.open('x') as output:
        output.write(f'{archive_sha}  {args.output.name}\n')
    print(f'{archive_sha}  {args.output}')


if __name__ == '__main__':
    main()
