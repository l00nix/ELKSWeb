#!/usr/bin/env python3
"""Compare native ELKS incremental scrolling with a forced full repaint.

F2 twice restores the same UI state while forcing full redraws. This checks
final pixels; host recording tests separately prove that strip redraw is used.
No HP hardware or reference-browser image is required.
"""
import argparse,json,pathlib,shutil,subprocess,tempfile,time
from parity import Machine,read_ppm,digest,install_frog_fixture
from live_qa import capture

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--image',type=pathlib.Path,required=True)
p.add_argument('--output',type=pathlib.Path,required=True)
a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
manifest=json.loads((pathlib.Path(__file__).parent/'candidate.example.json').read_text())
result={'image_sha256':digest(a.image),'cases':{},'timing_claim':None}
section='''<h2>Scroll section</h2><p><b>Bold</b> <i>italic</i> <u>underlined text</u></p>
<img src="/root/frog/frog.gif" width="174" height="80" alt="Frog">
<img src="missing.gif" width="120" height="40" alt="Missing image label">
<table border="1"><tr><td>Table edge</td><td>Second cell</td></tr></table>
<form><input name="q" value="Text field"><input type="checkbox" checked><input type="submit" value="Go"></form>
<p><a href="/root/frog/index.htm">Offline home</a></p>'''
for mode in ('cga','ega','vga'):
    out=a.output/mode;out.mkdir();machine=None;record={'checks':{},'captures':[]};result['cases'][mode]=record
    try:
        with tempfile.TemporaryDirectory(prefix='ew-scroll-native-') as tmp:
            work=pathlib.Path(tmp);im=work/'test.img';shutil.copyfile(a.image,im)
            install_frog_fixture(im,'/root/frog')
            for name,value in [('scroll.htm','<title>Scrolling regression</title>'+section*5),
                               ('qaurl','/root/scroll.htm\n'),('qavideo',mode+'\n')]:
                f=work/name;f.write_text(value)
                subprocess.run(['mcopy','-o','-i',str(im),str(f),'::/root/'+name],check=True,capture_output=True)
            argv=[v.format(image=im,qmp=work/'qmp.sock') for v in manifest['argv']]
            machine=Machine(argv,work/'qmp.sock',out/'qemu.log');time.sleep(12)
            record['captures'].append(capture(machine,out,'initial'))
            def key(value):
                machine.command('human-monitor-command',{'command-line':'sendkey '+value+' 25'});time.sleep(.3)
            actions=['down']*4+['up','pgdn','pgup','end','down','home','f3','down','f2','down','up','f3','tab','down']
            for i,action in enumerate(actions):
                key(action);time.sleep(.25)
                name=f'{i:02d}-{action}'
                record['captures'].append(capture(machine,out,name))
                before=read_ppm((out/(name+'.ppm')).read_bytes())
                key('f2');key('f2');time.sleep(.25)
                record['captures'].append(capture(machine,out,name+'-full'))
                after=read_ppm((out/(name+'-full.ppm')).read_bytes())
                record['checks'][name]=before==after
                if before!=after:raise AssertionError('Incremental/full mismatch: '+name)
            key('esc');record['captures'].append(capture(machine,out,'restored'))
            record['status']='pass'
    except Exception as e:record.update(status='error',error=str(e))
    finally:
        if machine:machine.close()
        (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(mode,record['status'],record.get('error',''),flush=True)
raise SystemExit(0 if all(c['status']=='pass' for c in result['cases'].values()) else 1)
