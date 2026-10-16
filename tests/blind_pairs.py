#!/usr/bin/env python3
"""Prepare identity-free paired PNGs; store randomized identity key outside review folder."""
import argparse,json,pathlib,random
from parity import normalize,read_ppm,png
p=argparse.ArgumentParser();p.add_argument('--run',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--balanced',action='store_true',help='Equal candidate-left and candidate-right views');p.add_argument('--suite',choices=['browser','tables','all'],default='browser');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
spec={'page-initial':('http','initial'),'form-focus':('forms','field'),'page-scrolled':('http','end'),'typography':('typography','initial')}
tables={'table-auto':('auto_columns','initial'),'table-explicit':('tablewidth','initial')}
if a.suite=='tables':spec=tables
elif a.suite=='all':spec.update(tables)
key={};rng=random.SystemRandom()
side_schedule=['reference']*(len(spec)//2)+['candidate']*(len(spec)//2);rng.shuffle(side_schedule)
if a.suite=='all':
 side_schedule=['reference','reference','candidate','candidate'];rng.shuffle(side_schedule)
 table_sides=['reference','candidate'];rng.shuffle(table_sides);side_schedule+=table_sides
for index,(name,(case,state)) in enumerate(spec.items()):
 pics={lane:normalize(read_ppm((a.run/lane/case/(state+'.ppm')).read_bytes())) for lane in ['reference','candidate']}
 lanes=['reference','candidate'];rng.shuffle(lanes)
 if a.balanced:lanes=[side_schedule[index], 'candidate' if side_schedule[index]=='reference' else 'reference']
 left,right=[pics[l] for l in lanes];assert left[:2]==right[:2]
 w,h=left[:2];pair=b''.join(left[2][y*w*3:(y+1)*w*3]+b'\x80'*24+right[2][y*w*3:(y+1)*w*3] for y in range(h));png(a.output/(name+'.png'),(w*2+8,h,pair));key[name]={'left':lanes[0],'right':lanes[1]}
a.output.with_name(a.output.name+'-key.json').write_text(json.dumps(key,indent=2)+'\n')
(a.output/'review-instructions.txt').write_text('Inspect only the supplied paired PNGs, independently. For each name choose LEFT, RIGHT or TIE, and identify concrete visual/readability/layout defects. Judge as a 640x200 monochrome browser. Do not infer identities. Screenshots do not establish functionality. Record a written verdict before any identity key is opened.\n')
print('\n'.join(str((a.output/(name+'.png')).resolve()) for name in spec))
