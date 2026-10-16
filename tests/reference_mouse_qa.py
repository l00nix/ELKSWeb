#!/usr/bin/env python3
"""Isolated real DOS MicroWeb mouse probe with its bundled CTMOUSE driver."""
import argparse,json,pathlib,shutil,subprocess,tempfile,time,types
from parity import FixtureServer,Machine,prepare_reference,digest
from live_qa import capture
p=argparse.ArgumentParser();p.add_argument('--reference-image',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parent.parent/'reference/freedos.boot.disk.720K.img');p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--fixture',choices=['radio','select'],default='radio');p.add_argument('--calibrate',action='store_true');p.add_argument('--port',type=int,default=18791);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
a.reference_image=a.reference_image.resolve();a.qemu=shutil.which('qemu-system-i386')
s=FixtureServer(a.port);machine=None;result={'reference_image_sha256':digest(a.reference_image),'driver':'Unmodified bundled CTMOUSE.EXE, invoked with no arguments','captures':[]}
def snap(name):result['captures'].append(capture(machine,a.output,name))
def hmp(command):machine.command('human-monitor-command',{'command-line':command});time.sleep(.2)
def move_small(dx,dy):
 while dx or dy:
  sx=max(-5,min(5,dx));sy=max(-5,min(5,dy))
  machine.command('human-monitor-command',{'command-line':f'mouse_move {sx} {sy}'});time.sleep(.05);dx-=sx;dy-=sy
 time.sleep(.5)
try:
 with tempfile.TemporaryDirectory(prefix='elksweb-reference-mouse-') as tmp:
  work=pathlib.Path(tmp);argv=prepare_reference(a,work,f'http://10.0.2.2:{a.port}/{a.fixture}.htm','http')
  auto=work/'AUTOEXEC.BAT';auto.write_bytes(auto.read_bytes().replace(b'MICROWEB ',b'CTMOUSE\r\nMICROWEB '));subprocess.run(['mcopy','-o','-i',str(work/'reference.img'),str(auto),'::AUTOEXEC.BAT'],check=True,capture_output=True)
  (a.output/'autoexec.bat').write_bytes(auto.read_bytes());(a.output/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,work/'qmp.sock',a.output/'qemu.log')
  deadline=time.monotonic()+30
  while not s.requests and time.monotonic()<deadline:time.sleep(.1)
  if not s.requests:raise TimeoutError('No radio fixture request')
  time.sleep(2);snap('initial');
  if a.calibrate:
   for i,(dx,dy) in enumerate([(10,10),(20,10),(5,5),(-5,-5)]):
    hmp(f'mouse_move {dx} {dy}');time.sleep(1);snap('calibration-%d'%i)
  else:
   move_small(-300,-300);snap('pointer-origin')
   if a.fixture=='radio':
    move_small(59,46);snap('pointer-radio-b');hmp('mouse_button 1');hmp('mouse_button 0');snap('radio-b-clicked');move_small(75,0)
   else:
    move_small(30,46);snap('pointer-select');hmp('mouse_button 1');hmp('mouse_button 0');snap('select-clicked')
    move_small(-18,8);snap('pointer-option');hmp('mouse_button 1');hmp('mouse_button 0');snap('option-clicked');move_small(50,-8)
   snap('pointer-submit');hmp('mouse_button 1');hmp('mouse_button 0');time.sleep(2);snap('submitted')
  result['requests']=s.requests;result['review']='pending visual pointer-position and submitted-query review'
finally:
 if machine:machine.close()
 s.close();(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
