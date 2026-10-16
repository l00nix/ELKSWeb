#!/usr/bin/env python3
"""Native control semantics, intentionally distinct from known reference bugs."""
import argparse,json,pathlib,shutil,types
from parity import CASES,FixtureServer,run_case,digest
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18792);p.add_argument('--grouped-radio',action='store_true');a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
a.qemu=shutil.which('qemu-system-i386');a.boot_timeout=30;a.settle=1.5;a.local_wait=10
manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());manifest['image']=str(a.image.resolve())
CASES['radio_action']['steps']=([('initial',None),('radio_a','tab'),('radio_b','down'),('submit','tab'),('submitted','ret')] if a.grouped_radio else [('initial',None),('radio_a','tab'),('radio_b','tab'),('selected','spc'),('submit','tab'),('submitted','ret')])
expectations={'radio_action':'/submit?pick=B','select_action':'/submit?choice=one','textarea_action':'/submit?notes=xfirst%0Asecond','field_limits':'/submit?text=abcseed&password=secretxyz','entities_form':'/submit?q=A%26B+%22Q%22+A+B'}
server=FixtureServer(a.port);summary={'image_sha256':digest(a.image),'grouped_radio':a.grouped_radio,'scope':'Actual native UI input and exact submitted requests; expected semantics deliberately avoid known reference defects.','results':{}}
try:
 for case in [*expectations,'anchors']:
  r=run_case(a,'candidate',case,server,manifest)
  if case in expectations:
   r['expected_submission']=expectations[case];r['submission_pass']=any(q['path']==expectations[case] for q in r['requests'])
  else:r['anchor_review']='Review jumped screenshot for visible BOTTOM TARGET; reload request alone is insufficient.'
  summary['results'][case]=r;print(case,r.get('submission_pass',r['anchor_review'] if case=='anchors' else None),flush=True)
finally:
 server.close();(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
