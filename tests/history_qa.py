#!/usr/bin/env python3
"""Actual native Backspace/toolbar history, branching, failed back and eight-entry limit."""
import argparse,json,pathlib,shutil,subprocess,tempfile,time
from parity import FixtureServer,Machine,digest,read_ppm,normalize
from live_qa import capture
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18796);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
s=FixtureServer(a.port);machine=None;r={'image_sha256':digest(a.image),'checks':{},'captures':[]};mouse=(320,100)
def key(k):machine.command('human-monitor-command',{'command-line':'sendkey '+k+' 25'});time.sleep(.05)
def text(t):
 m={':':'shift-semicolon','/':'slash','.':'dot','?':'shift-slash','=':'equal','-':'minus'}
 for c in t:key(m.get(c,c))
def snap(n):r['captures'].append(capture(machine,a.output,n))
def path(i):return '/next.htm?history='+str(i)
def navigate(i):
 key('ctrl-l');text(f'http://10.0.2.2:{a.port}'+path(i));key('ret');time.sleep(1.2)
def back():key('backspace');time.sleep(1.2)
def forward():
 global mouse
 machine.command('human-monitor-command',{'command-line':f'mouse_move {48-mouse[0]} {14-mouse[1]}'})
 time.sleep(.2);machine.command('human-monitor-command',{'command-line':'mouse_button 1'});time.sleep(.1);machine.command('human-monitor-command',{'command-line':'mouse_button 0'});time.sleep(1.2);mouse=(48,14)
def last():return s.requests[-1]['path']
try:
 with tempfile.TemporaryDirectory(prefix='elksweb-history-') as tmp:
  w=pathlib.Path(tmp);im=w/'candidate.img';shutil.copyfile(a.image,im)
  for name,value in [('qaurl','/root/welcome.htm\n'),('qaproxy','\n')]:
   f=w/name;f.write_text(value);subprocess.run(['mcopy','-o','-i',str(im),str(f),'::/root/'+name],check=True,capture_output=True)
  manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());argv=[v.format(image=im,qmp=w/'qmp.sock') for v in manifest['argv']]
  (a.output/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,w/'qmp.sock',a.output/'qemu.log')
  time.sleep(10);snap('initial-local')
  initial=normalize(read_ppm((a.output/'initial-local.ppm').read_bytes()))
  navigate(0)
  deadline=time.monotonic()+30
  while not s.requests and time.monotonic()<deadline:time.sleep(.1)
  if not s.requests:raise TimeoutError('No initial request')
  time.sleep(2);n=len(s.requests);back();snap('back-to-local')
  returned=normalize(read_ppm((a.output/'back-to-local.ppm').read_bytes()))
  r['checks']['http_back_to_local_no_request']=len(s.requests)==n
  r['checks']['http_back_to_local_content']=initial[2][22*640*3:192*640*3]==returned[2][22*640*3:192*640*3]
  n=len(s.requests);forward();r['checks']['local_forward_to_http']=len(s.requests)==n+1 and last()==path(0)
  navigate(1);navigate(2);back();r['checks']['backspace']=last()==path(1);snap('back-to-one')
  forward();r['checks']['toolbar_forward']=last()==path(2);snap('forward-to-two')
  back();navigate('branch');n=len(s.requests);forward();r['checks']['branch_discards_forward']=len(s.requests)==n;snap('branch-no-forward')
  back();s.fail_paths.add(path(0));back();r['checks']['failed_back_requested_previous']=last()==path(0) and s.requests[-1].get('injected_fault')=='truncated_body';snap('failed-back')
  s.fail_paths.clear();forward();r['checks']['failed_back_preserves_index']=last()==path('branch');snap('forward-after-failure')
  for i in range(3,12):navigate(i)
  n=len(s.requests)
  for _ in range(8):back()
  observed=[q['path'] for q in s.requests[n:]];expected=[path(i) for i in range(10,3,-1)]
  r['checks']['eight_entry_limit']=observed==expected;r['history_limit_observed']=observed;r['history_limit_expected']=expected;snap('oldest-retained-entry')
  r['status']='completed';r['requests']=s.requests
except Exception as e:r['status']='error';r['error']=str(e)
finally:
 if machine:machine.close()
 s.close();(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['captures','requests']},indent=2))
