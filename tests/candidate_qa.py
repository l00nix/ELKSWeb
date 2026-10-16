#!/usr/bin/env python3
"""Run named fixture interactions against one pinned native image."""
import argparse,json,pathlib,shutil
from parity import CASES,FixtureServer,run_case,digest
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18799);p.add_argument('--cases',nargs='+',choices=list(CASES),required=True);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
a.qemu=shutil.which('qemu-system-i386');a.boot_timeout=30;a.settle=2;a.local_wait=10
m=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());m['image']=str(a.image.resolve());s=FixtureServer(a.port);r={'image_sha256':digest(a.image),'cases':{}}
try:
 for c in a.cases:r['cases'][c]=run_case(a,'candidate',c,s,m);print(c,r['cases'][c]['functional_pass'],flush=True)
finally:s.close();(a.output/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
