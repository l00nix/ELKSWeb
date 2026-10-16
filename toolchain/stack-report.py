#!/usr/bin/env python3
"""Retain per-function GCC stack estimates; these are not call-chain bounds."""
import pathlib, sys
root=pathlib.Path(sys.argv[1])
rows=[]
for path in sorted((root/'obj').glob('*.su')):
    for line in path.read_text().splitlines():
        fields=line.split('\t')
        if len(fields)!=3: raise SystemExit('Unexpected stack usage row: '+line)
        location,amount,kind=fields
        rows.append((int(amount),location,kind))
if not rows: raise SystemExit('No GCC stack usage files generated')
rows.sort(reverse=True)
text='GCC per-function stack estimates (bytes), descending.\nThese exclude transitive callees, interrupts, argv/env, and hand-written assembly.\n\n'
text+='\n'.join('%6d  %-18s %s'%(size,kind,location) for size,location,kind in rows)+'\n'
(root/'stack-usage.txt').write_text(text)
print('STACK_USAGE largest individual frame: %d bytes %s (%s)'%rows[0])
for size,location,kind in rows:
    if size>=2048 or ('dynamic' in kind and 'bounded' not in kind): print('STACK_REVIEW %d bytes %s (%s)'%(size,location,kind))
