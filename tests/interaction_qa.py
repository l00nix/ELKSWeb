#!/usr/bin/env python3
"""Native QEMU mouse/address-edit/long-address/exit evidence with real input.
Coordinates are explicit parameters and must match an inspected fixture render.
"""
import argparse,json,pathlib,shutil,tempfile,time,subprocess
from parity import FixtureServer,Machine,digest
from live_qa import capture

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18788);p.add_argument('--relaunch',action='store_true');p.add_argument('--link-x',type=int,default=15);p.add_argument('--link-y',type=int,default=59);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
s=FixtureServer(a.port);machine=None;results={'image_sha256':digest(a.image),'mouse_target':[a.link_x,a.link_y],'captures':[]}
def key(k):machine.command('human-monitor-command',{'command-line':'sendkey '+k+' 25'});time.sleep(.06)
def text(value):
    mapping={' ':'spc',':':'shift-semicolon','/':'slash','.':'dot','?':'shift-slash','=':'equal','&':'shift-7','-':'minus','_':'shift-minus'}
    for c in value:key(mapping.get(c,c))
def snap(name):results['captures'].append(capture(machine,a.output,name))
try:
 with tempfile.TemporaryDirectory(prefix='elksweb-input-') as tmp:
    work=pathlib.Path(tmp);image=work/'candidate.img';shutil.copyfile(a.image,image)
    for name,value in [('qaurl',f'http://10.0.2.2:{a.port}/parity.htm\n'),('qaproxy','\n')]:
        f=work/name;f.write_text(value);subprocess.run(['mcopy','-o','-i',str(image),str(f),'::/root/'+name],check=True,capture_output=True)
    argv=[shutil.which('qemu-system-i386'),'-machine','isapc','-cpu','486','-m','8M','-accel','tcg,one-insn-per-tb=on','-display','none','-monitor','none','-serial','none','-qmp',f'unix:{work}/qmp.sock,server=on,wait=off','-drive',f'file={image},if=floppy,format=raw,snapshot=on','-boot','a','-netdev','user,id=net0','-device','ne2k_isa,netdev=net0,irq=3,iobase=0x300','-vga','std','-snapshot']
    (a.output/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,work/'qmp.sock',a.output/'qemu.log')
    deadline=time.monotonic()+30
    while not s.requests and time.monotonic()<deadline:time.sleep(.1)
    if not s.requests:raise TimeoutError('No initial fixture request')
    time.sleep(2);snap('initial')
    before=len(s.requests)
    machine.command('human-monitor-command',{'command-line':f'mouse_move {a.link_x-320} {a.link_y-100}'});time.sleep(.4);snap('mouse-position')
    machine.command('human-monitor-command',{'command-line':'mouse_button 1'});time.sleep(.15);machine.command('human-monitor-command',{'command-line':'mouse_button 0'});time.sleep(2);snap('mouse-click')
    results['mouse_click_followed_link']=any(r['path']=='/next.htm' for r in s.requests[before:])
    key('ctrl-l');time.sleep(.15);url=f'http://10.0.2.2:{a.port}/next.htm?edit=abc';text(url);key('left');key('backspace');key('x');snap('address-edited');before=len(s.requests);key('ret');time.sleep(2);snap('address-loaded')
    results['address_edit_expected_path']='/next.htm?edit=axc';results['address_edit_pass']=any(r['path']=='/next.htm?edit=axc' for r in s.requests[before:])
    key('ctrl-l');time.sleep(.15);url=f'http://10.0.2.2:{a.port}/next.htm?long='+'x'*280;text(url);snap('long-address');before=len(s.requests);key('ret');time.sleep(2);snap('long-address-loaded')
    results['long_address_typed_length']=len(url);results['long_address_expected_path']=url.split(f':{a.port}',1)[1];results['long_address_requests']=s.requests[before:];results['long_address_exact']=any(r['path']==results['long_address_expected_path'] for r in s.requests[before:])
    key('esc');time.sleep(1);snap('after-exit');results['exit_review']='Inspect text-mode screenshot and subsequent shell response; no automatic terminal-restoration pass asserted.'
    if a.relaunch:
        # Generic QA image explicitly has root with an empty password in /etc/passwd.
        text('root');key('ret');time.sleep(1);snap('after-root-login')
        before=len(s.requests);text('/bin/elksweb '+f'http://10.0.2.2:{a.port}/next.htm?relaunch=1');key('ret');time.sleep(3);snap('relaunched')
        results['relaunch_exact_request']=any(r['path']=='/next.htm?relaunch=1' for r in s.requests[before:])
        key('esc');time.sleep(1);snap('after-second-exit')
    results['requests']=s.requests;results['status']='completed_input_sequence'
except Exception as exc:results['status']='error';results['error']=str(exc)
finally:
 if machine:machine.close()
 s.close();(a.output/'result.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({k:v for k,v in results.items() if k not in ['captures','requests','long_address_requests','long_address_expected_path']},indent=2))
