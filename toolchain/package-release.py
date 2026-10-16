#!/usr/bin/env python3
"""Assemble private runtime, corresponding-source or optional test-image archives.

No builds, publication, disk-device access or in-place image changes. Identical
inputs produce identical bytes with the same Python/zlib. Source and binary
packages must be offered together; a checksum is not a runtime test result.
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

APP_SHA = '5c652079e7cc27884091c9e3b1730fea5d37fa3cbeb690535fed94af16dcfce2'
APP_REV = 'a3a5f1115576416c50f09ab5338f802ca8354300'
ELKS_REV = '89d09706f17c123f9e0f5ef7cba2eb6745e8478c'
FIXTURES = ('index.htm', 'http.htm', 'results.htm', 'article.htm', 'images.htm',
            'frog.gif', 'COPYING.txt', 'PROVENANCE.json', 'README.txt')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def committed_source(repo, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Source revision must be a full lowercase Git commit ID')
    if git(repo, 'rev-parse', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Source revision did not resolve exactly')
    raw = git(repo, 'archive', '--format=tar', revision)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files = {m.name: archive.extractfile(m).read()
                 for m in archive.getmembers() if m.isfile()}
    return raw, files


def elks_source(path, expected_hash, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('ELKS revision must be a full lowercase Git commit ID')
    original = path.read_bytes()
    if digest(original) != expected_hash:
        raise ValueError('ELKS source input SHA256 mismatch')
    raw = gzip.decompress(original) if original[:2] == b'\x1f\x8b' else original
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        if archive.pax_headers.get('comment') != revision:
            raise ValueError('ELKS archive Git commit header mismatch')
        licenses = [m for m in archive.getmembers() if m.isfile()
                    and pathlib.PurePosixPath(m.name).name == 'LICENSE']
        if not licenses:
            raise ValueError('ELKS source LICENSE missing')
        depth = min(len(pathlib.PurePosixPath(m.name).parts) for m in licenses)
        licenses = [m for m in licenses if len(pathlib.PurePosixPath(m.name).parts) == depth]
        if len(licenses) != 1:
            raise ValueError('Ambiguous top-level ELKS LICENSE')
        license_data = archive.extractfile(licenses[0]).read()
        notices = []
        for member in archive.getmembers():
            # Preserve upstream notices verbatim. This is a conservative libc
            # notice collection, not a claim that every listed module is linked.
            parts = pathlib.PurePosixPath(member.name).parts
            if not member.isfile():
                continue
            relative = parts if parts and parts[0] == 'libc' else parts[1:]
            if len(relative) < 2 or relative[0] != 'libc':
                continue
            if 'watcom' in parts or 'c86' in parts:
                continue
            content = archive.extractfile(member).read()
            if pathlib.PurePosixPath(member.name).name == 'LICENSE':
                blocks = [content]
            else:
                blocks = [block for block in re.findall(rb'/\*.*?\*/', content, re.S)
                          if re.search(rb'copyright|permission|licen[cs]e', block, re.I)]
            if blocks:
                notices.append(member.name.encode() + b'\n' + b'\n\n'.join(blocks))
        if not notices:
            raise ValueError('No ELKS libc notices found in source archive')
        notice_data = (b'Upstream ELKS libc notices (conservative collection).\n'
                       b'Full component sources accompany the separate corresponding-source archive.\n'
                       b'This does not assert that all listed modules are linked.\n\n'
                       + b'\n\n'.join(notices) + b'\n')
    return raw, license_data, notice_data


def checked_binary(build):
    binary = (build / 'elksweb').read_bytes()
    elf = (build / 'elksweb.elf').read_bytes()
    audit_raw = (build / 'isa-audit.json').read_bytes()
    audit = json.loads(audit_raw)
    if digest(binary) != APP_SHA:
        raise ValueError('Executable is not the approved unchanged ELKSWeb 0.1 binary')
    if (not audit.get('isa_static_pass') or not audit.get('memory', {}).get('memory_gate_pass')
            or audit.get('executable_sha256') != digest(binary)
            or audit.get('elf_sha256') != digest(elf)):
        raise ValueError('Passing ISA/memory report must match executable and ELF')
    return binary, audit_raw


def checked_image(build, expected_hash, binary, source):
    image = (build / 'elksweb.img').read_bytes()
    if len(image) != 2880 * 1024 or digest(image) != expected_hash:
        raise ValueError('Image must be the expected 2.88 MB artifact')
    checks = {'bin/elksweb': binary, 'root/welcome.htm': source['share/welcome.htm'],
              'root/elksweb.gif': source['share/elksweb.gif'],
              'root/logo-src.txt': source['share/logo-source.txt'], 'root/qavideo': b'\n'}
    for name in FIXTURES:
        guest = 'source.txt' if name == 'PROVENANCE.json' else name
        checks['root/frog/' + guest] = source['tests/fixtures/frogfind/' + name]
    with tempfile.TemporaryDirectory(prefix='elksweb-package-check-') as directory:
        tmp = pathlib.Path(directory)
        (tmp / 'image.img').write_bytes(image)
        for i, (guest, expected) in enumerate(checks.items()):
            destination = tmp / str(i)
            subprocess.run(['mcopy', '-i', str(tmp / 'image.img'),
                            '::/' + guest, str(destination)], check=True)
            actual = destination.read_bytes()
            if guest == 'root/qavideo':
                if actual.rstrip(b'\n'):
                    raise ValueError('Test image must retain interactive display selector')
            elif actual != expected:
                raise ValueError('Image content mismatch: ' + guest)
    return image


def write_archive(output, prefix, files, epoch):
    sidecar = output.with_name(output.name + '.sha256')
    if output.exists() or sidecar.exists():
        raise ValueError('Output or checksum sidecar exists; choose a new path')
    if not output.parent.is_dir():
        raise ValueError('Output parent directory must already exist')
    files['SHA256SUMS'] = ''.join(f'{digest(data)}  {name}\n'
                                for name, data in sorted(files.items())).encode()
    with output.open('xb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for name, data in sorted(files.items()):
                    member = tarfile.TarInfo(prefix + name)
                    member.size, member.mtime = len(data), epoch
                    member.mode = 0o755 if name in ('bin/elksweb', 'toolchain/run-qemu.sh') else 0o644
                    member.uid = member.gid = 0
                    member.uname = member.gname = ''
                    archive.addfile(member, io.BytesIO(data))
    archive_hash = digest(output.read_bytes())
    with sidecar.open('x') as stream:
        stream.write(f'{archive_hash}  {output.name}\n')
    return archive_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', required=True, choices=('runtime', 'source', 'test-image'))
    parser.add_argument('--revision', required=True, help='Full committed release source SHA')
    parser.add_argument('--binary-revision', default=APP_REV, help='Commit used for approved executable')
    parser.add_argument('--build-dir', type=pathlib.Path, help='elksweb, ELF, ISA report; image for test-image')
    parser.add_argument('--image-sha256', help='Required for test-image')
    parser.add_argument('--elks-source', required=True, type=pathlib.Path, help='Pinned ELKS Git tar[.gz], also supplies runtime notices')
    parser.add_argument('--elks-source-sha256', required=True, help='Expected ELKS source archive SHA256')
    parser.add_argument('--elks-revision', default=ELKS_REV)
    parser.add_argument('--notes', required=True, type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parent.parent
    try:
        source_tar, source = committed_source(repo, args.revision)
        _, binary_source = committed_source(repo, args.binary_revision)
        # A documentation/help-only commit may package an unchanged executable.
        # Fail closed for any compiled source/header/font/image data change.
        compiled = lambda files: {n: data for n, data in files.items()
                                  if n.startswith(('src/', 'platform/', 'image/', 'font/'))
                                  and n.endswith(('.c', '.h'))}
        if compiled(source) != compiled(binary_source):
            raise ValueError('Compiled inputs differ from --binary-revision; rebuild/revalidate required')
        if args.binary_revision != APP_REV:
            raise ValueError('Binary revision must match the pinned approved 0.1 executable')
        epoch = int(git(repo, 'show', '-s', '--format=%ct', args.revision))
        elks_tar, license_data, libc_notices = elks_source(
            args.elks_source, args.elks_source_sha256, args.elks_revision)
        files = {'RELEASE-NOTES.md': args.notes.read_bytes(),
                 'licenses/ELKS-LICENSE.txt': license_data,
                 'licenses/ELKS-libc-notices.txt': libc_notices}
        for name in ('COPYING', 'font/COPYING', 'font/provenance.json'):
            files[name] = source[name]
        metadata = {'version': '0.1', 'kind': args.kind, 'visibility': 'private',
                    'browser_revision': args.revision, 'binary_revision': args.binary_revision,
                    'browser_source_tar_sha256': digest(source_tar),
                    'binary_sha256': APP_SHA, 'source_date_epoch': epoch,
                    'elks_revision': args.elks_revision,
                    'elks_source_input_sha256': args.elks_source_sha256,
                    'runtime_validation': 'See supplied release notes; assembly is not a runtime test.',
                    'reproducibility': 'Identical inputs and Python/zlib yield identical archive bytes.'}
        if args.kind != 'source':
            if not args.build_dir:
                raise ValueError('--build-dir is required for runtime/test-image')
            binary, audit = checked_binary(args.build_dir)
            files['validation/isa-audit.json'] = audit
        if args.kind == 'runtime':
            files['bin/elksweb'] = binary
            for name in ('share/welcome.htm', 'share/elksweb.gif'):
                files[name] = source[name]
            for name, data in source.items():
                if name.startswith('share/') and name.endswith(('.txt', '.md')):
                    files[name] = data
            readme = '''Install on a compatible ELKS system with a graphics console and writable /tmp:
  copy bin/elksweb to /bin/elksweb (make it executable)
  copy share/welcome.htm to /root/welcome.htm
  copy share/elksweb.gif to /root/elksweb.gif
  retain share/logo-source.txt as /root/logo-src.txt
Run: elksweb
Choose CGA, EGA or VGA. Escape exits. The default local help page documents keys
and supported features. A URL or local file can also be supplied on the command line.

HP 200LX with this project's ELKS 3.8beta1 setup:
  export ELKSWEB_COOKED_KEYS=1
  elksweb -video cga /root/welcome.htm
Use the existing compatible HP installation; this archive does not install ELKS.

No offline website fixtures or webfrog/webnews launchers are included.
Keep COPYING and font/COPYING with redistributed copies. The separate source
archive provides browser and ELKS sources, font provenance and build instructions.
Offer that corresponding-source archive alongside this runtime archive.
'''
        else:
            files['source/ELKS-source.tar.gz'] = gzip.compress(elks_tar, mtime=0)
            files['licenses/ELKS-LICENSE.txt'] = license_data
            files['source/ELKSWeb-source.tar.gz'] = gzip.compress(source_tar, mtime=0)
            if args.kind == 'source':
                readme = '''Corresponding source for the matching ELKSWeb 0.1 runtime archive.
Extract source/ELKSWeb-source.tar.gz and source/ELKS-source.tar.gz; follow
ELKSWeb docs/BUILDING.md. The source commit and approved executable hash are
recorded in PACKAGE.json. Help/doc-only changes may postdate the binary commit.

The complete ELKS source retains component-specific licenses, including libc.
Browser source is GPL-2.0-or-later; the independently derived fonts retain their Adobe/DEC
permission notice and provenance. Repository test fixtures and documentation
screenshots retain attribution; website content belongs to its providers.
'''
            else:
                if not args.image_sha256:
                    raise ValueError('--image-sha256 is required for test-image')
                files['build/elksweb.img'] = checked_image(args.build_dir, args.image_sha256, binary, source)
                files['toolchain/run-qemu.sh'] = source['toolchain/run-qemu.sh']
                for name in FIXTURES:
                    files['fixtures/frogfind/' + name] = source['tests/fixtures/frogfind/' + name]
                files['docs/BUILDING.md'] = source['docs/BUILDING.md']
                files['docs/config/elks-generic.config'] = source['docs/config/elks-generic.config']
                metadata['image_sha256'] = args.image_sha256
                readme = '''Optional generic ELKS/QEMU test image; not an HP installer.
Install qemu-system-i386 and mtools, then from this directory run:
  bash toolchain/run-qemu.sh
  bash toolchain/run-qemu.sh /root/frog/index.htm
  bash toolchain/run-qemu.sh /root/frog/images.htm
  bash toolchain/run-qemu.sh http://68k.news/
The launcher uses a disposable image copy and a 486 CPU, not an 8088.
Saved guest files disappear after exit. The default display selector remains enabled.

The image contains attributed fixed FrogFind sample pages under /root/frog.
These samples are separate from normal runtime installation and are not live search.
Captured 68k.news archives and webfrog/webnews launchers are not packaged here.
Complete browser/ELKS source and component notices accompany this test image;
ELKS kernel/userspace and the attributed FrogFind fixtures have distinct licenses.
'''
        files['README.txt'] = ('ELKSWeb 0.1 — PRIVATE ' + args.kind + ' package\n\n'
                               + readme + '\nRead RELEASE-NOTES.md for validation scope and limitations.\n'
                               'Verify extracted files: sha256sum -c SHA256SUMS\n'
                               'The outer .sha256 checks the archive. Hashes are not signatures.\n').encode()
        files['PACKAGE.json'] = (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode()
        result = write_archive(args.output, 'ELKSWeb-0.1-' + args.kind + '/', files, epoch)
        print(f'{result}  {args.output}')
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
