#!/usr/bin/env python3
"""Package committed ELKSWeb 0.2 source and an audited executable; never publish."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path

# Keep the pinned 0.1 packaging policy intact; reuse deterministic archive and
# upstream-source/notice verification helpers only.
spec = importlib.util.spec_from_file_location('archive_helpers', Path(__file__).with_name('package-release.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision', required=True, help='Exact committed source used for the build')
    p.add_argument('--build-dir', type=Path, required=True)
    p.add_argument('--binary-sha256', required=True)
    p.add_argument('--elks-source', type=Path, required=True)
    p.add_argument('--elks-source-sha256', required=True)
    p.add_argument('--elks-revision', required=True)
    p.add_argument('--output-dir', type=Path, required=True, help='Existing empty directory')
    a = p.parse_args()
    repo = Path(__file__).resolve().parent.parent
    source_tar, source = h.committed_source(repo, a.revision)
    if b'#define EW_VERSION "0.2"' not in source['src/version.h']:
        p.error('Source is not version 0.2')
    if not a.output_dir.is_dir() or any(a.output_dir.iterdir()):
        p.error('Output directory must exist and be empty')
    binary = (a.build_dir / 'elksweb').read_bytes()
    audit = json.loads((a.build_dir / 'isa-audit.json').read_bytes())
    if (h.digest(binary) != a.binary_sha256 or
            audit.get('executable_sha256') != a.binary_sha256 or
            audit.get('elf_sha256') != h.digest((a.build_dir / 'elksweb.elf').read_bytes()) or
            not audit.get('isa_static_pass') or
            not audit.get('memory', {}).get('memory_gate_pass')):
        p.error('Binary, ELF and passing ISA/memory audit must agree')
    # The caller builds from git archive of --revision. Retain that input hash
    # in the build directory and verify it, rather than guessing from a worktree.
    if (a.build_dir / 'source-tar.sha256').read_text().split()[0] != h.digest(source_tar):
        p.error('Build source archive does not match the committed source')
    elks_tar, elks_license, libc_notices = h.elks_source(
        a.elks_source, a.elks_source_sha256, a.elks_revision)
    epoch = int(h.git(repo, 'show', '-s', '--format=%ct', a.revision))
    license_text = (source['share/license.txt'] + b'\n\nELKS license\n============\n' +
                    elks_license + b'\n\nELKS libc notices\n=================\n' + libc_notices)
    metadata = dict(version='0.2', browser_revision=a.revision,
                    binary_revision=a.revision, binary_sha256=a.binary_sha256,
                    browser_source_tar_sha256=h.digest(source_tar),
                    elks_revision=a.elks_revision,
                    elks_source_input_sha256=a.elks_source_sha256,
                    source_date_epoch=epoch,
                    validation='See release notes; checksums and packaging are not hardware tests.')
    common = {'RELEASE-NOTES.md': source['docs/RELEASE-0.2.md'],
              'CHANGELOG.md': source['CHANGELOG.md'],
              'COPYING': source['COPYING'], 'font/COPYING': source['font/COPYING'],
              'font/provenance.json': source['font/provenance.json'],
              'licenses/ELKS-LICENSE.txt': elks_license,
              'licenses/ELKS-libc-notices.txt': libc_notices}
    for kind in ('runtime', 'source'):
        files = dict(common)
        files['PACKAGE.json'] = (json.dumps(dict(metadata, kind=kind), indent=2, sort_keys=True)+'\n').encode()
        if kind == 'runtime':
            files['bin/elksweb'] = binary
            for src, dst in [('welcome.htm','welcome.htm'), ('elksweb.gif','elksweb.gif'),
                             ('logo-source.txt','logo-src.txt')]:
                files['lib/elksweb/'+dst] = source['share/'+src]
            files['lib/elksweb/license.txt'] = license_text
            readme = '''ELKSWeb 0.2 experimental beta runtime

Install bin/elksweb as /bin/elksweb and chmod 755 /bin/elksweb.
Create /lib/elksweb and copy lib/elksweb/* there, including license.txt.
A graphics console and writable /tmp are required. Run elksweb --version,
then elksweb from the graphics console. Configure networking and run net start
before loading HTTP sites. No operating system or disk image is installed.
See RELEASE-NOTES.md and the online docs/INSTALL.md for limits and mouse setup.
Keep notices and the matching corresponding-source archive with redistribution.
Verify extracted files on a modern host: sha256sum -c SHA256SUMS
'''
        else:
            files['source/ELKSWeb-source.tar.gz'] = gzip.compress(source_tar, mtime=0)
            files['source/ELKS-source.tar.gz'] = gzip.compress(elks_tar, mtime=0)
            readme = '''ELKSWeb 0.2 corresponding source

Extract both archives under source/ into separate directories. Follow the browser
source docs/BUILDING.md and ELKS build documentation. PACKAGE.json records the
exact browser and ELKS revisions and the executable hash. Fonts retain their
public-domain notices and provenance. ELKS components retain their own licenses.
The prepared ELKS IA16 toolchain is required; no Nano-X dependency is added.
Verify extracted files on a modern host: sha256sum -c SHA256SUMS
'''
        files['README.txt'] = readme.encode()
        path = a.output_dir / ('ELKSWeb-0.2-'+kind+'.tar.gz')
        print(h.write_archive(path, 'ELKSWeb-0.2-'+kind+'/', files, epoch), path.name)
    (a.output_dir / 'elksweb').write_bytes(binary)
    (a.output_dir / 'elksweb').chmod(0o755)
    (a.output_dir / 'elksweb.sha256').write_text(a.binary_sha256+'  elksweb\n')
    assets = sorted(x for x in a.output_dir.iterdir() if not x.name.endswith('.sha256'))
    (a.output_dir / 'SHA256SUMS').write_text(''.join(h.digest(x.read_bytes())+'  '+x.name+'\n' for x in assets))


if __name__ == '__main__':
    main()
