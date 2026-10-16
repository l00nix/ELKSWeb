#!/usr/bin/env python3
"""Capture the real default help/logo on disposable ELKS QEMU images.

This exercises no-URL startup, the third-link help anchor, scrolling, inversion
and console restoration. Geometry/pixel checks complement manual frame review;
they do not establish physical 8088 behavior or timing.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
from parity import Machine, digest, read_ppm
from live_qa import capture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--modes',nargs='+',choices=('cga','ega','vga'),default=['cga','ega','vga'])
    parser.add_argument('--memory',help='Override QEMU -m; default keeps candidate manifest setting')
    parser.add_argument('--console-command-test',action='store_true',help='After exit, log into the empty-password generic root and run an echo marker')
    args=parser.parse_args()
    args.image=args.image.resolve();args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    root=pathlib.Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'tests/candidate.example.json').read_text())
    result={'image_sha256':digest(args.image),'default_url':'/root/welcome.htm',
            'launch_without_url_argument':True,'cases':{},'visual_review':'pending',
            'scope':'QEMU 486 integration; no physical hardware/timing claim',
            'memory':args.memory or manifest['argv'][manifest['argv'].index('-m')+1],
            'console_command_test_requested':args.console_command_test}
    for mode,selection,height in [('cga','1',200),('ega','2',350),('vga','3',480)]:
        if mode not in args.modes:continue
        out=args.output/mode;out.mkdir();machine=None
        record={'checks':{},'captures':[]};result['cases'][mode]=record
        try:
            with tempfile.TemporaryDirectory(prefix='ew-welcome-') as tmp:
                work=pathlib.Path(tmp);image=work/'test.img';shutil.copyfile(args.image,image)
                for guest,name in [('::/bin/elksweb','binary'),('::/root/welcome.htm','welcome.htm'),
                                   ('::/root/elksweb.gif','elksweb.gif'),('::/etc/rc.sys','rc.sys')]:
                    subprocess.run(['mcopy','-i',str(image),guest,str(work/name)],check=True,capture_output=True)
                record['binary_sha256']=digest(work/'binary')
                record['help_sha256']=digest(work/'welcome.htm')
                record['logo_sha256']=digest(work/'elksweb.gif')
                assert (work/'welcome.htm').read_bytes()==(root/'share/welcome.htm').read_bytes()
                assert (work/'elksweb.gif').read_bytes()==(root/'share/elksweb.gif').read_bytes()
                startup=(work/'rc.sys').read_text()
                # Use the actual compiled-in default URL, with no URL argument.
                assert 'exec /bin/elksweb "$url"' in startup
                startup=startup.replace('exec /bin/elksweb "$url"','exec /bin/elksweb')
                (work/'rc.sys').write_text(startup)
                (work/'qavideo').write_text('\n')
                for name,guest in [('rc.sys','/etc/rc.sys'),('qavideo','/root/qavideo')]:
                    subprocess.run(['mcopy','-o','-i',str(image),str(work/name),'::'+guest],check=True,capture_output=True)
                argv=[v.format(image=image,qmp=work/'qmp.sock') for v in manifest['argv']]
                if args.memory:argv[argv.index('-m')+1]=args.memory
                (out/'command.json').write_text(json.dumps(argv,indent=2)+'\n')
                machine=Machine(argv,work/'qmp.sock',out/'qemu.log');time.sleep(10)
                def shot(name):
                    image_info=capture(machine,out,name);record['captures'].append(image_info)
                    return image_info
                def key(value):
                    machine.command('human-monitor-command',{'command-line':'sendkey '+value+' 25'})
                    time.sleep(.35)
                menu=shot('selector');key(selection);key('ret');time.sleep(4)
                initial=shot('initial')
                record['checks']['mode_geometry']=initial['width']==640 and initial['height']==height
                for _ in range(3):key('tab')
                shot('keyboard-help-focused');key('ret');time.sleep(5);shot('keyboard-help-anchor')
                key('pgdn');shot('page-down');key('end');shot('end')
                key('home');shot('home')
                before=read_ppm((out/'home.ppm').read_bytes())
                key('f2');shot('inverted');key('f2');shot('normal-restored')
                restored=read_ppm((out/'normal-restored.ppm').read_bytes())
                record['checks']['double_invert_exact']=before==restored
                # Body should return to its original top even with #keys in address.
                original=read_ppm((out/'initial.ppm').read_bytes())
                def content(picture):
                    width,h,pixels=picture
                    # QEMU CGA physical scanlines may be doubled.
                    scale=h//height;stride=width*3
                    return b''.join(pixels[y*stride:y*stride+624*3]
                                    for y in range(22*scale,(height-8)*scale))
                record['checks']['home_restores_initial_content']=content(original)==content(before)
                key('esc');time.sleep(2);console=shot('console-restored')
                record['checks']['console_geometry_restored']=(console['width'],console['height'])==(menu['width'],menu['height'])
                if args.console_command_test:
                    for letter in 'root':key(letter)
                    key('ret');time.sleep(2);shot('root-login')
                    for letter in 'echo welcomeexitok':key('spc' if letter==' ' else letter)
                    key('ret');time.sleep(2);shot('console-command')
                    record['console_command']='echo welcomeexitok; visible output needs screenshot review'
                if not all(record['checks'].values()):raise AssertionError(record['checks'])
                record['status']='checks_pass_visual_review_pending'
        except Exception as exc:
            record.update(status='error',error=str(exc))
        finally:
            if machine:machine.close()
            (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(mode,record['status'],record.get('error',''),flush=True)
    if digest(args.image)!=result['image_sha256']:raise AssertionError('Input image changed')
    return 1 if any(c['status']=='error' for c in result['cases'].values()) else 0

if __name__=='__main__':raise SystemExit(main())
