#!/usr/bin/env python3
"""Native MIME rendering and download input, exact saved bytes on isolated FAT image.
Never mutates the supplied image. QEMU writes only a new disposable test copy.
"""
import argparse,hashlib,json,pathlib,shutil,subprocess,tempfile,time
from parity import FixtureServer,Machine,digest
from live_qa import capture
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--port',type=int,default=18793);p.add_argument('--disk-full',action='store_true');a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
s=FixtureServer(a.port);machine=None;results={'image_sha256':digest(a.image),'disk_full_lane':a.disk_full,'captures':[]}
def key(k):machine.command('human-monitor-command',{'command-line':'sendkey '+k+' 25'});time.sleep(.07)
def text(value):
 mapping={' ':'spc',':':'shift-semicolon','/':'slash','.':'dot','?':'shift-slash','=':'equal','&':'shift-7','-':'minus','_':'shift-minus'}
 for c in value:key(mapping.get(c,c))
def snap(name):results['captures'].append(capture(machine,a.output,name))
def navigate(path):
 key('ctrl-l');time.sleep(.1);text(f'http://10.0.2.2:{a.port}'+path);key('ret');time.sleep(3)
try:
 with tempfile.TemporaryDirectory(prefix='elksweb-download-') as tmp:
  work=pathlib.Path(tmp);image=work/'candidate.img';shutil.copyfile(a.image,image)
  for name,value in [('qaurl',f'http://10.0.2.2:{a.port}'+('/download-large.bin' if a.disk_full else '/literal.txt')+'\n'),('qaproxy','\n')]:
   f=work/name;f.write_text(value);subprocess.run(['mcopy','-o','-i',str(image),str(f),'::/root/'+name],check=True,capture_output=True)
  if a.disk_full:
   import re
   listing=subprocess.check_output(['mdir','-i',str(image),'::'],text=True)
   free=int(re.search(r'([\d ]+) bytes free',listing).group(1).replace(' ',''))
   filler=work/'fill.bin';filler.write_bytes(b'F'*max(0,free-300000))
   subprocess.run(['mcopy','-i',str(image),str(filler),'::/fill.bin'],check=True,capture_output=True)
   results['free_space_before_boot']=subprocess.check_output(['mdir','-i',str(image),'::'],text=True)
  argv=[shutil.which('qemu-system-i386'),'-machine','isapc','-cpu','486','-m','8M','-accel','tcg,one-insn-per-tb=on','-display','none','-monitor','none','-serial','none','-qmp',f'unix:{work}/qmp.sock,server=on,wait=off','-drive',f'file={image},if=floppy,format=raw','-boot','a','-netdev','user,id=net0','-device','ne2k_isa,netdev=net0,irq=3,iobase=0x300','-vga','std']
  (a.output/'command.json').write_text(json.dumps(argv,indent=2)+'\n');machine=Machine(argv,work/'qmp.sock',a.output/'qemu.log')
  deadline=time.monotonic()+40
  while not s.requests and time.monotonic()<deadline:time.sleep(.1)
  if not s.requests:raise TimeoutError('No initial fixture request')
  time.sleep(20 if a.disk_full else 4);snap('initial')
  if a.disk_full:
   key('ret');time.sleep(10);snap('disk-full-save-result');key('esc');time.sleep(.3)
  else:
   navigate('/image.gif');snap('direct-gif')
   navigate('/direct.png');snap('direct-png')
   navigate('/download.bin');snap('download-prompt');key('ret');time.sleep(2);snap('saved')
   navigate('/download.bin');key('ret');time.sleep(1);snap('existing-file-error');key('esc');time.sleep(.5);snap('existing-file-cancelled')
   navigate('/download.bin');key('esc');time.sleep(.5);snap('cancelled')
   navigate('/download.bin');key('home');key('delete');key('slash');key('end')
   for _ in range(3):key('backspace')
   text('dat');key('left');key('right');snap('filename-edited');key('ret');time.sleep(2);snap('edited-filename-saved')
  # Exit to login, enter the documented empty-password generic QA root account,
  # and sync FAT buffers before reading the isolated image from the host.
  key('esc');time.sleep(1);text('root');key('ret');time.sleep(1);text('sync');key('ret');time.sleep(2);snap('synced-shell')
  machine.close();machine=None
  saved=a.output/'download.bin';copy=subprocess.run(['mcopy','-i',str(image),'::/root/download.bin',str(saved)],capture_output=True,text=True)
  results['download_file_exists']=copy.returncode==0
  if not a.disk_full:
   expected=bytes(range(256))*16+b'ELKSWEB-END\0'
   results['saved_bytes_exact']=copy.returncode==0 and saved.read_bytes()==expected
   results['expected_size']=len(expected);results['expected_sha256']=hashlib.sha256(expected).hexdigest()
   if saved.exists():results['actual_size']=saved.stat().st_size;results['actual_sha256']=digest(saved)
   edited=a.output/'download.dat';second=subprocess.run(['mcopy','-i',str(image),'::/root/download.dat',str(edited)],capture_output=True,text=True)
   results['edited_filename_bytes_exact']=second.returncode==0 and edited.read_bytes()==expected
  else:results['partial_file_removed']=copy.returncode!=0
  results['file_read_stderr']=copy.stderr;results['requests']=s.requests;results['status']='completed_input_sequence'
except Exception as exc:results['status']='error';results['error']=str(exc)
finally:
 if machine:machine.close()
 s.close();(a.output/'result.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({k:v for k,v in results.items() if k not in ['captures','requests']},indent=2))
