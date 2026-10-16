#!/usr/bin/env python3
"""Separate live-site evidence. Never substitutes a local fixture or proxy.

The supplied FrogFind mirror is used; original frogfind.com is skipped.
Mirror failures/timeouts are skipped for this run only and always retried
on the next invocation. No dynamic screenshots enter deterministic parity.
"""
import argparse, datetime, hashlib, json, pathlib, re, shutil, subprocess, tempfile, time
from parity import Machine, prepare_reference, read_ppm, normalize, png, digest

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent.parent
SITES={'frogfind':'http://frogfind.8088retro.com/','68k':'http://68k.news/'}

def capture(machine,directory,name):
    raw=directory/(name+'.ppm');machine.capture(raw);pic=read_ppm(raw.read_bytes())
    normalized=True
    try:pic=normalize(pic)
    except ValueError:normalized=False
    png(directory/(name+'.png'),pic)
    return {'png':name+'.png','width':pic[0],'height':pic[1],'normalized_cga':normalized,'sha256':hashlib.sha256(pic[2]).hexdigest()}

def observe_pcap(path):
    data=path.read_bytes() if path.exists() else b''
    # Evidence hints only: packet boundaries/retransmissions are not reassembled.
    statuses=list(dict.fromkeys(x.decode('ascii','replace') for x in re.findall(rb'HTTP/1\.[01] [0-9]{3}[^\r\n]{0,80}',data)))
    requests=list(dict.fromkeys(x.decode('ascii','replace') for x in re.findall(rb'(?:GET|POST) [^\r\n]{1,2048} HTTP/1\.[01]',data)))
    return {'http_status_lines_observed':statuses,'request_lines_observed':requests,'pcap_bytes':len(data),'interpretation':'Raw-packet hints only; inspect screenshot and pcap. An HTTP status is not proof of successful final page rendering.'}

def run(args,lane,name,url):
    out=args.output/lane/name;out.mkdir(parents=True)
    timeout=args.news_timeout if name=='68k' and args.news_timeout is not None else args.timeout
    result={'lane':lane,'site':name,'url':url,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'timeout_seconds':timeout,'proxy':None,'captures':[],'status':'error','review':'pending screenshot review'}
    machine=None
    with tempfile.TemporaryDirectory(prefix='elksweb-live-') as temp:
        work=pathlib.Path(temp)
        try:
            if lane=='reference':
                argv=prepare_reference(args,work,url,'http')
                result['source_image_sha256']=digest(args.reference_image)
            else:
                image=work/'candidate.img';shutil.copyfile(args.candidate_image,image);result['source_image_sha256']=digest(image)
                for name_,value in [('qaurl',url+'\n'),('qaproxy','\n'),('qavideo','cga\n')]:
                    p=work/name_;p.write_text(value);subprocess.run(['mcopy','-o','-i',str(image),str(p),'::/root/'+name_],check=True,capture_output=True)
                argv=[args.qemu,'-machine','isapc','-cpu','486','-m','8M','-accel','tcg,one-insn-per-tb=on','-display','none','-monitor','none','-serial','none','-qmp',f'unix:{work}/qmp.sock,server=on,wait=off','-drive',f'file={image},if=floppy,format=raw,snapshot=on','-boot','a','-netdev','user,id=net0','-device','ne2k_isa,netdev=net0,irq=3,iobase=0x300','-vga','std','-snapshot']
            pcap=out/'traffic.pcap';argv+=['-object',f'filter-dump,id=livecapture,netdev=net0,file={pcap}']
            (out/'command.json').write_text(json.dumps(argv,indent=2)+'\n')
            machine=Machine(argv,work/'qmp.sock',out/'qemu.log');started=time.monotonic()
            for delay,label in [(min(10,timeout),'early'),(timeout,'final')]:
                remaining=delay-(time.monotonic()-started)
                if remaining>0:time.sleep(remaining)
                shot=capture(machine,out,label);shot['elapsed_seconds']=round(time.monotonic()-started,2);result['captures'].append(shot)
            if getattr(args,'exercise_frogfind',False) and name=='frogfind':
                def key(value):
                    machine.command('human-monitor-command',{'command-line':'sendkey '+value+' 25'});time.sleep(.12)
                key('tab')
                for letter in 'elks linux':key('spc' if letter==' ' else letter)
                result['captures'].append(capture(machine,out,'mirror-query-entered'))
                key('tab');key('ret');time.sleep(args.article_timeout)
                result['captures'].append(capture(machine,out,'mirror-search-results'))
                # Live mirror markup inspected: home link, query field, submit, first article.
                for _ in range(4):key('tab')
                result['captures'].append(capture(machine,out,'mirror-first-article-focused'))
                key('ret');time.sleep(args.article_timeout)
                result['captures'].append(capture(machine,out,'mirror-article-result'))
                key('backspace');time.sleep(args.article_timeout)
                result['captures'].append(capture(machine,out,'mirror-back-to-results'))
                result['mirror_actions']={'query':'elks linux','first_result_tab_count':4,'observation_seconds_each':args.article_timeout,'interpretation':'Live search and article, without fixture substitution. Inspect focus, actual GET and rendered content; upstream error is not a browser pass.'}
            if args.exercise_news and name=='68k':
                machine.key('pgdn');time.sleep(1);result['captures'].append(capture(machine,out,'news-page2'))
                machine.key('end');time.sleep(1);result['captures'].append(capture(machine,out,'news-end'))
                machine.key('home');time.sleep(.5)
                # Observed live page order:12masthead/navigation links precede first article.
                for _ in range(13):machine.command('human-monitor-command',{'command-line':'sendkey tab 25'});time.sleep(.12)
                result['captures'].append(capture(machine,out,'news-first-article-focused'))
                machine.key('ret');time.sleep(args.article_timeout);result['captures'].append(capture(machine,out,'news-article-result'))
                machine.key('backspace');time.sleep(args.article_timeout);result['captures'].append(capture(machine,out,'news-back-to-home'))
                result['news_actions']={'keys':['PageDown','End','Home']+['Tab']*13+['Enter'],'article_observation_seconds':args.article_timeout,'interpretation':'Focus target must be confirmed visually; inspect actual request line to verify full articleURL and final redirect/error behavior.'}
            result.update(observe_pcap(pcap));result['status']='captured_live_attempt'
            if not result['http_status_lines_observed']:
                result['status']='skipped_this_run' if name=='frogfind' else 'no_http_response_within_window'
                result['reason']='No HTTP response status observed within bounded capture window; screenshot/pcap review required to distinguish timeout, DNS or other failure.'
            if name=='frogfind':result['retry_next_run']=True
        except Exception as exc:
            result['error']=str(exc)
            if name=='frogfind':result['status']='skipped_this_run';result['retry_next_run']=True
        finally:
            if machine:machine.close()
            result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--lanes',nargs='+',choices=['reference','candidate'],default=['reference','candidate']);p.add_argument('--sites',nargs='+',choices=list(SITES),default=list(SITES))
    p.add_argument('--timeout',type=float,default=35);p.add_argument('--qemu',default=shutil.which('qemu-system-i386'))
    p.add_argument('--news-timeout',type=float,help='Optional separate 68k observation window,1..180seconds; FrogFind keeps --timeout')
    p.add_argument('--exercise-frogfind',action='store_true',help='Search live mirror for elks linux, follow first article and return')
    p.add_argument('--exercise-news',action='store_true',help='After initial 68k capture, PageDown/End/Home and Tab13+Enter for article observation')
    p.add_argument('--article-timeout',type=float,default=20)
    p.add_argument('--reference-image',type=pathlib.Path,default=HERE.parent/'reference/freedos.boot.disk.720K.img');p.add_argument('--candidate-image',type=pathlib.Path,default=HERE.parent/'build/elksweb.img')
    a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    if not 1<=a.timeout<=60:p.error('timeout must be 1..60 seconds per site')
    if a.news_timeout is not None and not 1<=a.news_timeout<=180:p.error('news-timeout must be 1..180 seconds')
    if not 1<=a.article_timeout<=60:p.error('article-timeout must be 1..60 seconds')
    results=[]
    for lane in a.lanes:
        for name in a.sites:
            result=run(a,lane,name,SITES[name]);results.append(result);print(lane,name,result['status'],flush=True)
    summary={'kind':'separate_live_site_evidence','deterministic_parity':False,'results':results,'skipped_original_site':{'url':'http://frogfind.com/','reason':'User reports original offline and supplied frogfind.8088retro.com mirror; original is not probed.'},'policy':'Always retry the supplied FrogFind mirror in the next run; a failed/timed-out current run is skipped only for this invocation. No fixture substitution, no HTTP proxy, no synthetic pages.'}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
