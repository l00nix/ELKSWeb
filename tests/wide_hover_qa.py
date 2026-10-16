#!/usr/bin/env python3
"""Actual native hover, horizontal clipping/scrolling and hit-testing after scroll."""
import argparse,json,pathlib,shutil,subprocess,tempfile,time
from parity import FixtureServer,Machine,digest
from live_qa import capture
p=argparse.ArgumentParser();p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18797);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
s=FixtureServer(a.port);machine=None;r={'image_sha256':digest(a.image),'captures':[]};mouse=(320,100)
def key(k):machine.command('human-monitor-command',{'command-line':'sendkey '+k+' 25'});time.sleep(.045)
def snap(n):r['captures'].append(capture(machine,a.output,n))
def move(x,y):
 global mouse
 machine.command('human-monitor-command',{'command-line':f'mouse_move {x-mouse[0]} {y-mouse[1]}'})
 time.sleep(.3);mouse=(x,y)
try:
 with tempfile.TemporaryDirectory(prefix='elksweb-wide-') as tmp:
  w=pathlib.Path(tmp);im=w/'candidate.img';shutil.copyfile(a.image,im)
  for name,value in [('qaurl',f'http://10.0.2.2:{a.port}/wide.htm\n'),('qaproxy','\n')]:
   f=w/name;f.write_text(value);subprocess.run(['mcopy','-o','-i',str(im),str(f),'::/root/'+name],check=True,capture_output=True)
  manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text());argv=[v.format(image=im,qmp=w/'qmp.sock') for v in manifest['argv']]
  (a.output/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,w/'qmp.sock',a.output/'qemu.log')
  deadline=time.monotonic()+30
  while not s.requests and time.monotonic()<deadline:time.sleep(.1)
  if not s.requests:raise TimeoutError('No initial request')
  time.sleep(2);snap('initial');move(15,26);snap('hover-start');move(320,100)
  for _ in range(100):key('right')
  time.sleep(.3);snap('right-edge');move(580,26);snap('hover-right-edge')
  n=len(s.requests);machine.command('human-monitor-command',{'command-line':'mouse_button 1'});time.sleep(.1);machine.command('human-monitor-command',{'command-line':'mouse_button 0'});time.sleep(2);snap('clicked-right-edge')
  r['scrolled_mouse_target']=[580,26];r['scrolled_link_exact_request']=any(q['path']=='/next.htm?wide=1' for q in s.requests[n:]);r['requests']=s.requests;r['status']='completed'
except Exception as e:r['status']='error';r['error']=str(e)
finally:
 if machine:machine.close()
 s.close();(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['captures','requests']},indent=2))
