#!/usr/bin/env python3
"""Native startup-menu, mode geometry and text-console restoration captures.

Each case uses an isolated FAT image. Screenshots require independent review;
geometry assertions alone do not establish correct rendering.
"""
import argparse,json,pathlib,shutil,subprocess,tempfile,time
from parity import Machine,digest,install_frog_fixture
from live_qa import capture
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--image',type=pathlib.Path,required=True)
p.add_argument('--output',type=pathlib.Path,required=True)
a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text())
result={'image_sha256':digest(a.image),'cases':{},'visual_review':'pending'}
for name,key,height in [('cga','1',200),('ega','2',350),('vga','3',480),('cancel','q',None),('invalid',None,None)]:
 machine=None;out=a.output/name;out.mkdir();record={'captures':[]};result['cases'][name]=record
 try:
  with tempfile.TemporaryDirectory(prefix='ew-display-') as tmp:
   work=pathlib.Path(tmp);im=work/'test.img';shutil.copyfile(a.image,im)
   rc=work/'rc.sys';subprocess.run(['mcopy','-i',str(im),'::/etc/rc.sys',str(rc)],check=True,capture_output=True)
   startup=rc.read_text()
   if 'exec /bin/elksweb -video cga "$url"' in startup:
    startup=startup.replace('exec /bin/elksweb -video cga "$url"','exec /bin/elksweb '+('-video invalid ' if name=='invalid' else '')+'"$url"')
    rc.write_text(startup);subprocess.run(['mcopy','-o','-i',str(im),str(rc),'::/etc/rc.sys'],check=True,capture_output=True)
   else:
    video=work/'qavideo';video.write_text('invalid\n' if name=='invalid' else '\n')
    subprocess.run(['mcopy','-o','-i',str(im),str(video),'::/root/qavideo'],check=True,capture_output=True)
   install_frog_fixture(im,'/root/frog')
   url=work/'qaurl';url.write_text('/root/frog/index.htm\n');subprocess.run(['mcopy','-o','-i',str(im),str(url),'::/root/qaurl'],check=True,capture_output=True)
   argv=[v.format(image=im,qmp=work/'qmp.sock') for v in manifest['argv']]
   machine=Machine(argv,work/'qmp.sock',out/'qemu.log');time.sleep(10)
   record['captures'].append(capture(machine,out,'startup'))
   if key:
    machine.key(key);time.sleep(.2);machine.key('ret');time.sleep(5)
    selected=capture(machine,out,'selected');record['captures'].append(selected)
    if height:
     record['geometry_pass']=selected['width']==640 and selected['height']==height
     machine.key('esc');time.sleep(2)
     restored=capture(machine,out,'restored');record['captures'].append(restored)
     record['text_geometry_restored']=restored['width']==record['captures'][0]['width'] and restored['height']==record['captures'][0]['height']
    else:record['cancel_geometry_preserved']=selected['width']==record['captures'][0]['width'] and selected['height']==record['captures'][0]['height']
   record['status']='captured'
 except Exception as error:record.update(status='error',error=str(error))
 finally:
  if machine:machine.close()
  (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
  print(name,json.dumps({k:v for k,v in record.items() if k!='captures'}),flush=True)
