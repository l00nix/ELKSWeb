#!/usr/bin/env python3
"""Native character-aware field editing with exact original-encoding submissions."""
import argparse,json,pathlib,shutil
from parity import CASES,FixtureServer,run_case,digest
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18801);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
a.qemu=shutil.which('qemu-system-i386');a.boot_timeout=30;a.settle=1;a.local_wait=10
m=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());m['image']=str(a.image.resolve())
specs={
 'utf8_untouched':('/utf8fields.htm',[],'/submit?q=A%C3%A9B'),
 'utf8_delete':('/utf8fields.htm',['home','right','delete'],'/submit?q=AB'),
 'utf8_backspace':('/utf8fields.htm',['end','left','backspace'],'/submit?q=AB'),
 'utf8_insert':('/utf8fields.htm',['home','right','right','x'],'/submit?q=A%C3%A9xB'),
 'utf8_password':('/utf8password.htm',[],'/submit?q=A%C3%A9B'),
 'legacy_untouched':('/charset.htm',[],'/submit?q=caf%E9'),
 'legacy_backspace':('/charset.htm',['end','backspace'],'/submit?q=caf'),
 'meta_untouched':('/metafields.htm',[],'/submit?q=%8A'),
}
s=FixtureServer(a.port);r={'image_sha256':digest(a.image),'cases':{}}
try:
 for name,(path,keys,expected) in specs.items():
  CASES[name]={'path':path,'requests':[path,'/submit'],'steps':[('initial',None),('focused','tab')]+[('edit%d'%i,key) for i,key in enumerate(keys)]+[('submit','tab'),('submitted','ret')]}
  q=run_case(a,'candidate',name,s,m);q['expected_submission']=expected;q['exact_submission_pass']=any(v['path']==expected for v in q['requests']);r['cases'][name]=q;print(name,q['exact_submission_pass'],flush=True)
finally:s.close();(a.output/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
