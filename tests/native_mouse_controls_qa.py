#!/usr/bin/env python3
"""Native mouse controls and wrapped-table links using reviewed CGA coordinates."""
import argparse,json,pathlib,shutil,subprocess,tempfile,time
from parity import FixtureServer,Machine,digest
from live_qa import capture
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18795);p.add_argument('--cases',nargs='+',choices=['select','radio','mapped','auto_columns'],default=['select','radio']);p.add_argument('--click',nargs=2,type=int,metavar=('X','Y'),help='Reviewed mouse target for auto_columns');a=p.parse_args()
if 'auto_columns' in a.cases and a.click is None:p.error('auto_columns requires --click X Y from a reviewed screenshot')
if a.click and not(0<=a.click[0]<640 and 0<=a.click[1]<200):p.error('click must lie within640x200')
a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
s=FixtureServer(a.port);results={'image_sha256':digest(a.image),'cases':{}}
try:
 for case,points,expected in [('select',[(33,27),(15,39),(75,27)],'/submit?choice=one'),('radio',[(71,27),(173,27)],'/submit?pick=B'),('mapped',[(16,38)],'/next.htm?8,8'),('auto_columns',[tuple(a.click)] if a.click else [],'/next.htm?autotable=1')]:
  if case not in a.cases:continue
  machine=None;out=a.output/case;out.mkdir();entry={'coordinates':points,'expected_request':expected,'captures':[]};start=len(s.requests)
  try:
   with tempfile.TemporaryDirectory(prefix='elksweb-mouse-') as tmp:
    work=pathlib.Path(tmp);image=work/'candidate.img';shutil.copyfile(a.image,image)
    page='auto-columns' if case=='auto_columns' else case
    for name,value in [('qaurl',f'http://10.0.2.2:{a.port}/{page}.htm\n'),('qaproxy','\n')]:
     f=work/name;f.write_text(value);subprocess.run(['mcopy','-o','-i',str(image),str(f),'::/root/'+name],check=True,capture_output=True)
    manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());argv=[v.format(image=image,qmp=work/'qmp.sock') for v in manifest['argv']]
    (out/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,work/'qmp.sock',out/'qemu.log')
    deadline=time.monotonic()+30
    while len(s.requests)==start and time.monotonic()<deadline:time.sleep(.1)
    if len(s.requests)==start:raise TimeoutError('No initial request')
    time.sleep(2);entry['captures'].append(capture(machine,out,'initial'));last=(320,100)
    for i,(x,y) in enumerate(points):
     machine.command('human-monitor-command',{'command-line':f'mouse_move {x-last[0]} {y-last[1]}'})
     time.sleep(.3);machine.command('human-monitor-command',{'command-line':'mouse_button 1'});time.sleep(.15);machine.command('human-monitor-command',{'command-line':'mouse_button 0'});time.sleep(1.5)
     entry['captures'].append(capture(machine,out,'click%d'%(i+1)));last=(x,y)
    entry['requests']=s.requests[start:];entry['exact_submission_pass']=any(r['path']==expected for r in entry['requests'])
  except Exception as e:entry['error']=str(e)
  finally:
   if machine:machine.close()
   results['cases'][case]=entry
finally:s.close();(a.output/'result.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({k:v.get('exact_submission_pass',v.get('error')) for k,v in results['cases'].items()}))
