#!/usr/bin/env python3
"""Actual DOS MicroWeb versus candidate QEMU: deterministic fixtures, honest gates.

Requires Python stdlib, qemu-system-i386 and mcopy. No HP hardware access.
Exit 0: measured parity passed (other gates may remain pending).
Exit 1: test/visual mismatch; exit 2: candidate pending.
"""
import argparse, hashlib, http.server, json, os, pathlib, random
import re, shutil, socket, struct, subprocess, tempfile, threading, time, zlib

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent.parent
FIXTURES=HERE/'fixtures'
# Fixed 16x16 black/white checker with a minimal, valid GIF LZW stream.
GIF=(FIXTURES/'image.gif').read_bytes()
FROG_FILES=('index.htm','http.htm','results.htm','article.htm','images.htm','frog.gif')
CASES={
    'frogfind_http': {'path':'/frogfind/http.htm','requests':['/frogfind/http.htm','/frogfind/frog.gif','/frogfind/results.htm','/frogfind/article.htm'],
                     'exact_requests':[{'method':'GET','path':'/frogfind/results.htm?q=ELKS'},{'method':'GET','path':'/frogfind/article.htm'}],
                     'steps':[('initial',None),('field','tab'),('submit','tab'),('results','ret'),('home_link','tab'),('article_link','tab'),('article','ret')]},
    'frogfind_images': {'path':'/frogfind/images.htm','requests':['/frogfind/images.htm','/frogfind/frog.gif'],
                       'steps':[('initial',None),('direct_link','tab'),('direct_image','ret')]},
    'frogfind_local': {'path':r'FROG\INDEX.HTM','local_folder':'frogfind','requests':[],
                      'steps':[('initial',None),('results_link','tab'),('results','ret'),('home_link','tab'),('article_link','tab'),('article','ret'),('back','backspace')]},
    'auto_columns': {'path':'/auto-columns.htm','requests':['/auto-columns.htm','/next.htm'],
                     'exact_requests':[{'method':'GET','path':'/next.htm?autotable=1'}],
                     'steps':[('initial',None),('end','end'),('home','home'),('focused','tab'),('followed','ret')]},
    'tablewidth': {'path':'/tablewidth.htm','requests':['/tablewidth.htm'],'steps':[('initial',None),('end','end')]},
    'alt': {'path':'/alt.htm','requests':['/alt.htm','/missing.gif','/direct.png'],'steps':[('initial',None)]},
    'fontsizes': {'path':'/fontsizes.htm','requests':['/fontsizes.htm'],'steps':[('initial',None)]},
    'charset': {'path':'/charset.htm','requests':['/charset.htm','/submit'],'steps':[('initial',None),('field','tab'),('submit','tab'),('submitted','ret')]},
    'tables': {'path':'/tables.htm','requests':['/tables.htm'],'steps':[('initial',None),('focused','tab'),('followed','ret')]},
    'wide': {'path':'/wide.htm','requests':['/wide.htm'],'steps':[('initial',None),('link1','tab'),('link2','tab')]},
    'plain_text': {'path':'/literal.txt','requests':['/literal.txt'],'steps':[('initial',None)]},
    'direct_gif': {'path':'/image.gif','requests':['/image.gif'],'steps':[('initial',None)]},
    'direct_png': {'path':'/direct.png','requests':['/direct.png'],'steps':[('initial',None)]},
    'binary_prompt': {'path':'/download.bin','requests':['/download.bin'],'steps':[('initial',None)]},
    'radio_action': {'path':'/radio.htm','requests':['/radio.htm','/submit'],'steps':[('initial',None),('focused','tab'),('selected','spc'),('submit','tab'),('submitted','ret')]},
    'textarea_action': {'path':'/textarea.htm','requests':['/textarea.htm','/submit'],'steps':[('initial',None),('focused','tab'),('edited','x'),('submit','tab'),('submitted','ret')]},
    'select_action': {'path':'/select.htm','requests':['/select.htm','/submit'],'steps':[('initial',None),('focused','tab'),('opened','ret'),('previous','up'),('selected','ret'),('submit','tab'),('submitted','ret')]},
    'form_inventory': {'path':'/formcontrols.htm','requests':['/formcontrols.htm'],'steps':[('initial',None)]+[('tab%d'%i,'tab') for i in range(1,9)]},
    'field_limits': {'path':'/controlsize.htm','requests':['/controlsize.htm','/submit'],'steps':[('initial',None),('text','tab'),('a','a'),('b','b'),('c','c'),('password','tab'),('x','x'),('y','y'),('z','z'),('submit','tab'),('submitted','ret')]},
    'anchors': {'path':'/anchors.htm','requests':['/anchors.htm'],'steps':[('initial',None),('focused','tab'),('jumped','ret'),('end','end')]},
    'entities_link': {'path':'/entities.htm','requests':['/entities.htm','/next.htm'],'steps':[('initial',None),('focused','tab'),('followed','ret')]},
    'entities_form': {'path':'/entities.htm','requests':['/entities.htm','/submit'],'steps':[('initial',None),('link','tab'),('field','tab'),('submit','tab'),('submitted','ret')]},
    'embedded_url': {'path':'/embedded.htm','requests':['/embedded.htm','/next.htm'],'steps':[('initial',None),('focused','tab'),('followed','ret')]},
    'typography': {'path':'/typography.htm','requests':['/typography.htm'],'steps':[('initial',None),('end','end')]},
    'local': {'path':'LOCAL.HTM','requests':[], 'steps':[('initial',None),('tab','tab')]},
    'http': {'path':'/parity.htm','requests':['/parity.htm','/image.gif'],
             'steps':[('initial',None),('tab','tab'),('end','end'),('home','home'),('address','ctrl-l')]},
    'redirect': {'path':'/redirect','requests':['/redirect','/next.htm'],'steps':[('initial',None)]},
    'relative_redirect': {'path':'/relative-redirect','requests':['/relative-redirect'],'steps':[('initial',None)],
                         'note':'Pinned MicroWeb displays Invalid protocol for relative Location; preserve evidence, do not mistake this for standards-correct behavior.'},
    'missing': {'path':'/missing','requests':['/missing'],'steps':[('initial',None)]},
    'navigation': {'path':'/parity.htm','requests':['/parity.htm','/image.gif','/next.htm'],
                   'steps':[('initial',None),('tab','tab'),('follow','ret')]},
    'forms': {'path':'/parity.htm','requests':['/parity.htm','/image.gif','/submit'],
              'steps':[('initial',None),('link1','tab'),('link2','tab'),('link3','tab'),('field','tab'),('submit','tab'),('submitted','ret')]},
    'controls': {'path':'/parity.htm','requests':['/parity.htm','/image.gif'],
                 'steps':[('initial',None),('inverted','f2'),('restored','f2'),('bars_hidden','f3'),('bars_restored','f3'),('reloaded','f5')]},
    'post_edit_checkbox': {'path':'/forms.htm','requests':['/forms.htm','/submit'],
                 'steps':[('initial',None),('field','tab'),('delete','backspace'),('edited','x'),('checkbox','tab'),('unchecked','spc'),('submit','tab'),('submitted','ret')]},
    'chunked': {'path':'/chunked','requests':['/chunked'],'steps':[('initial',None)]},
    'truncated': {'path':'/truncated','requests':['/truncated'],'steps':[('initial',None)]},
    'malformed': {'path':'/malformed','requests':['/malformed'],'steps':[('initial',None)]},
    'redirect_loop': {'path':'/loop','requests':['/loop'],'steps':[('initial',None)]},
    'large': {'path':'/large.htm','requests':['/large.htm'],'initial_wait':10,'steps':[('initial',None),('end','end'),('home','home')]},
    'proxy': {'path':'http://fixture.invalid/proxy.htm','proxy':True,'requests':['http://fixture.invalid/proxy.htm'],'steps':[('initial',None)]},
}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_ppm(data):
    # Consume exactly one separator after maxval: pixel bytes may be whitespace.
    match=re.match(rb'P6\s+(\d+)\s+(\d+)\s+255(?:\r\n|\s)',data)
    if not match:raise ValueError('Unsupported PPM (requires P6 RGB8 without comments)')
    w,h=map(int,match.groups());pixels=data[match.end():]
    if len(pixels)!=w*h*3:raise ValueError('Truncated/oversized PPM')
    return w,h,pixels

def normalize(picture):
    w,h,p=picture
    if (w,h)==(640,200):return picture
    if (w,h)==(640,400):
        stride=w*3
        for y in range(0,h,2):
            if p[y*stride:(y+1)*stride]!=p[(y+1)*stride:(y+2)*stride]:
                raise ValueError('640x400 is not exact CGA row doubling; cannot silently resize')
        return w,200,b''.join(p[y*stride:(y+1)*stride] for y in range(0,h,2))
    raise ValueError(f'Unexpected geometry {w}x{h}; expected CGA 640x200')

def png(path,picture):
    w,h,p=picture
    def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    rows=b''.join(b'\0'+p[y*w*3:(y+1)*w*3] for y in range(h))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))

def compare_pixels(a,b):
    if a[:2]!=b[:2]:return {'same_geometry':False,'pass':False,'reference_size':a[:2],'candidate_size':b[:2]}
    n=sum(a[2][i:i+3]!=b[2][i:i+3] for i in range(0,len(a[2]),3))
    return {'same_geometry':True,'different_pixels':n,'total_pixels':a[0]*a[1], 'fraction':n/(a[0]*a[1]),'pass':n==0}

class FixtureServer:
    def __init__(self,port):
        self.requests=[]
        self.fail_paths=set()
        outer=self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version='HTTP/1.0'
            def log_message(self,*args):pass
            def do_POST(self):
                length=int(self.headers.get('Content-Length','0'))
                if length>4096:self.send_error(413);return
                data=self.rfile.read(length)
                body=b'<html><title>POST submitted</title><body><h1>Form received</h1><p>'+data+b'</p></body></html>'
                outer.requests.append({'method':'POST','path':self.path,'status':200,'body_sha256':hashlib.sha256(body).hexdigest(),'request_body':data.decode('ascii','replace')})
                self.send_response_only(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def do_GET(self):
                path=self.path.split('?',1)[0]
                if self.path in outer.fail_paths:
                    body=b'Injected truncated fixture'
                    outer.requests.append({'method':'GET','path':self.path,'status':200,'body_sha256':hashlib.sha256(body).hexdigest(),'injected_fault':'truncated_body'})
                    self.connection.sendall(b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 999\r\n\r\n'+body);self.close_connection=True;return
                if path in ['/chunked','/truncated','/malformed']:
                    body=b'<html><title>Framing fixture</title><body><h1>Framed body</h1></body></html>'
                    if path=='/chunked':raw=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n'+('%x\r\n'%len(body)).encode()+body+b'\r\n0\r\n\r\n'
                    elif path=='/truncated':raw=b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 999\r\n\r\n'+body
                    else:raw=b'INVALID STATUS\r\n\r\n'+body
                    outer.requests.append({'method':'GET','path':self.path,'status':None if path=='/malformed' else 200,'body_sha256':hashlib.sha256(body).hexdigest(),'wire_sha256':hashlib.sha256(raw).hexdigest()})
                    self.connection.sendall(raw);self.close_connection=True;return
                if path in ['/redirect','/relative-redirect','/loop']:status,body,kind=302,b'Redirect','text/plain'
                elif path.startswith('/frogfind/') and path[10:] in FROG_FILES:status,body,kind=200,(FIXTURES/'frogfind'/path[10:]).read_bytes(),'image/gif' if path.endswith('.gif') else 'text/html'
                elif path=='/image.gif':status,body,kind=200,GIF,'image/gif'
                elif path=='/charset.htm':status,body,kind=200,b'<html><title>Legacy charset</title><body><h1>caf\xe9 \x93quote\x94 \x80</h1><p>Cr\xe8me br\xfbl\xe9e</p><form action="/submit"><input name="q" value="caf\xe9"><input type="submit" value="Send"></form></body></html>','text/html; charset=windows-1252'
                elif path=='/literal.txt':status,body,kind=200,b'<h1>Literal markup</h1> &amp; remains literal\nWi.!    spaced\n1234\tcolumn\nLast line','text/plain'
                elif path=='/download.bin':status,body,kind=200,bytes(range(256))*16+b'ELKSWEB-END\0','application/octet-stream'
                elif path=='/download-large.bin':status,body,kind=200,(bytes(range(256))*782)[:200000],'application/octet-stream'
                elif path=='/direct.png':status,body,kind=200,(FIXTURES/'direct.png').read_bytes(),'image/png'
                elif path in ['/auto-columns.htm','/tablewidth.htm','/parity.htm','/next.htm','/forms.htm','/embedded.htm','/typography.htm','/formcontrols.htm','/controlsize.htm','/anchors.htm','/entities.htm','/radio.htm','/textarea.htm','/select.htm','/wide.htm','/tables.htm','/alt.htm','/mapped.htm','/fontsizes.htm','/utf8fields.htm','/utf8password.htm','/metafields.htm']:status,body,kind=200,(FIXTURES/path[1:]).read_bytes(),'text/html'
                elif path=='/large.htm':status,body,kind=200,b'<html><title>Resource fixture</title><body><h1>Resource boundary</h1>'+b'<p>Repeated bounded fixture line.</p>'*2000+b'<p>END MARKER</p></body></html>','text/html'
                elif path=='http://fixture.invalid/proxy.htm':status,body,kind=200,b'<html><title>Proxy fixture</title><body><h1>Proxy reached</h1></body></html>','text/html'
                elif path=='/submit':status,body,kind=200,b'<html><title>Submitted</title><body>Form received</body></html>','text/html'
                else:status,body,kind=404,b'<html><title>Missing fixture</title><body><h1>404 fixture</h1></body></html>','text/html'
                outer.requests.append({'method':'GET','path':self.path,'status':status,'body_sha256':hashlib.sha256(body).hexdigest()})
                self.send_response_only(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
                if status==302:self.send_header('Location','/next.htm' if path=='/relative-redirect' else f'http://10.0.2.2:{outer.server.server_port}'+('/loop' if path=='/loop' else '/next.htm'))
                self.end_headers()
                try:self.wfile.write(body)
                except BrokenPipeError:pass
        self.server=http.server.HTTPServer(('127.0.0.1',port),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()

class Machine:
    def __init__(self,argv,qmp,log):
        self.log=log.open('wb');self.process=subprocess.Popen(argv,stdout=self.log,stderr=self.log)
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.socket.settimeout(10)
        try:
            for _ in range(200):
                if self.process.poll() is not None:raise RuntimeError('QEMU exited during startup; see qemu.log')
                try:self.socket.connect(str(qmp));break
                except (FileNotFoundError,ConnectionRefusedError):time.sleep(.05)
            else:raise TimeoutError('QMP startup')
            self.file=self.socket.makefile('rwb',buffering=0);self.file.readline();self.command('qmp_capabilities')
        except Exception:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.socket.close();self.log.close();raise
    def command(self,name,args=None):
        self.file.write((json.dumps({'execute':name,**({'arguments':args} if args else {})})+'\n').encode())
        while True:
            raw=self.file.readline()
            if not raw:raise RuntimeError('QMP disconnected')
            reply=json.loads(raw)
            if 'error' in reply:raise RuntimeError(reply['error'])
            if 'return' in reply:return reply['return']
    def key(self,key):self.command('human-monitor-command',{'command-line':'sendkey '+key})
    def capture(self,path):self.command('screendump',{'filename':str(path)})
    def close(self):
        try:
            if self.process.poll() is None:self.command('quit')
            self.process.wait(timeout=5)
        except Exception:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        finally:self.socket.close();self.log.close()

def install_frog_fixture(image,guest_dir):
    """Copy only8.3 fixture resources into an isolated guest image."""
    made=subprocess.run(['mmd','-i',str(image),'::'+guest_dir],capture_output=True)
    if made.returncode:
        subprocess.run(['mdir','-i',str(image),'::'+guest_dir],check=True,capture_output=True)
    for name in FROG_FILES:
        subprocess.run(['mcopy','-o','-i',str(image),str(FIXTURES/'frogfind'/name),'::'+guest_dir+'/'+name],check=True,capture_output=True)

def prepare_reference(args,work,url,case):
    image=work/'reference.img';shutil.copyfile(args.reference_image,image)
    if CASES[case].get('local_folder'):install_frog_fixture(image,'/frog')
    proxy=f'SET HTTP_PROXY=10.0.2.2:{args.port}\r\n' if CASES[case].get('proxy') else ''
    files={'CONFIG.SYS':'FILES=20\r\nBUFFERS=20\r\nSHELL=A:\\COMMAND.COM /E:512 /P\r\n',
           'AUTOEXEC.BAT':f'@ECHO OFF\r\nNE2000 0x60 3 0x300\r\nSET MTCPCFG=MTCP.CFG\r\nDHCP\r\n{proxy}MICROWEB -video=a {url}\r\n'}
    for name,data in files.items():(work/name).write_bytes(data.encode('ascii'))
    shutil.copyfile(FIXTURES/'local.htm',work/'LOCAL.HTM')
    for name in [*files,'LOCAL.HTM']:
        subprocess.run(['mcopy','-o','-i',str(image),str(work/name),'::'+name],check=True,capture_output=True)
    return [args.qemu,'-machine','isapc','-cpu','486','-m','8M','-display','none','-monitor','none','-serial','none',
            '-qmp',f'unix:{work}/qmp.sock,server=on,wait=off','-drive',f'file={image},if=floppy,format=raw,snapshot=on',
            '-boot','a','-netdev','user,id=net0','-device','ne2k_isa,netdev=net0,irq=3,iobase=0x300','-vga','std','-snapshot']

def run_case(args,lane,case,server,manifest):
    target=args.output/lane/case;target.mkdir(parents=True)
    spec=CASES[case];is_local=case=='local' or bool(spec.get('local_folder'));url=spec['path'] if is_local else spec['path'] if spec.get('proxy') else f'http://10.0.2.2:{args.port}'+spec['path']
    result={'case':case,'lane':lane,'url':url,'captures':{},'status':'error'}
    start=len(server.requests);machine=None
    with tempfile.TemporaryDirectory(prefix='elksweb-parity-') as tmp:
        work=pathlib.Path(tmp)
        try:
            if lane=='reference':argv=prepare_reference(args,work,url,case)
            else:
                values={'qmp':str(work/'qmp.sock'),'port':args.port,'url':url,'case':case,'fixture_dir':str(FIXTURES),'output':str(target)}
                if 'image' in manifest:
                    candidate_image=work/'candidate.img';shutil.copyfile(manifest['image'],candidate_image)
                    result['boot_image_sha256']=digest(candidate_image)
                    values['image']=str(candidate_image)
                    local_guest=manifest.get('local_fixture_path','/root/local.htm')
                    if spec.get('local_folder'):
                        install_frog_fixture(candidate_image,'/root/frog')
                        local_guest='/root/frog/index.htm'
                    if is_local:result['url']=local_guest
                    url_file=work/'qaurl';url_file.write_text((local_guest if is_local else url)+'\n')
                    subprocess.run(['mcopy','-o','-i',str(candidate_image),str(url_file),'::'+manifest.get('url_file','/root/qaurl')],check=True,capture_output=True)
                    if not spec.get('local_folder'):subprocess.run(['mcopy','-o','-i',str(candidate_image),str(FIXTURES/'local.htm'),'::'+local_guest],check=True,capture_output=True)
                    proxy_file=work/'qaproxy';proxy_file.write_text((f'10.0.2.2:{args.port}' if spec.get('proxy') else '')+'\n')
                    subprocess.run(['mcopy','-o','-i',str(candidate_image),str(proxy_file),'::'+manifest.get('proxy_file','/root/qaproxy')],check=True,capture_output=True)
                argv=[str(v).format(**values) for v in manifest['argv']]
                if not any('snapshot=on' in arg for arg in argv) and '-snapshot' not in argv:argv.append('-snapshot')
            (target/'command.json').write_text(json.dumps(argv,indent=2)+'\n')
            machine=Machine(argv,work/'qmp.sock',target/'qemu.log')
            deadline=time.monotonic()+args.boot_timeout
            if is_local:time.sleep(args.local_wait)
            else:
                while len(server.requests)==start and time.monotonic()<deadline:time.sleep(.1)
                if len(server.requests)==start:raise TimeoutError('No fixture HTTP request before deadline')
                time.sleep(max(args.settle,spec.get('initial_wait',0)))
            for state,key in spec['steps']:
                if key:machine.key(key);time.sleep(args.settle)
                raw=target/(state+'.ppm');machine.capture(raw)
                pic=normalize(read_ppm(raw.read_bytes()));png(target/(state+'.png'),pic)
                result['captures'][state]={'png':str((target/(state+'.png')).relative_to(args.output)),'ppm':str(raw.relative_to(args.output)),'width':pic[0],'height':pic[1],'sha256':hashlib.sha256(pic[2]).hexdigest()}
            result['status']='captured'
        except Exception as exc:result['error']=str(exc)
        finally:
            if machine:machine.close()
    result['requests']=server.requests[start:]
    paths=[r['path'].split('?',1)[0] for r in result['requests']]
    result['missing_requests']=[p for p in spec['requests'] if p not in paths]
    result['missing_exact_requests']=[expected for expected in spec.get('exact_requests',[])
                                      if not any(all(actual.get(k)==v for k,v in expected.items())
                                                 for actual in result['requests'])]
    result['functional_pass']=result['status']=='captured' and not result['missing_requests'] and not result['missing_exact_requests']
    result['functional_scope']='Required request presence, optional exact method/path/body assertions, and successful capture; comparison adds full trace equality and pixels. Functional scope is only the named fixture actions.'
    (target/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def make_comparison(args,reference,candidate):
    results=[];secret={};rng=random.SystemRandom();out=args.output/'comparison';out.mkdir()
    for case,ref in reference.items():
        cand=candidate.get(case,{})
        for state,capture in ref.get('captures',{}).items():
            name=f'{case}-{state}';entry={'case':case,'state':state}
            if state not in cand.get('captures',{}):entry.update({'pass':False,'error':'Candidate capture missing'});results.append(entry);continue
            a=normalize(read_ppm((args.output/capture['ppm']).read_bytes()));b=normalize(read_ppm((args.output/cand['captures'][state]['ppm']).read_bytes()))
            entry.update(compare_pixels(a,b));results.append(entry)
            if a[:2]!=b[:2]:continue
            w,h=a[:2];diff=bytes(channel for i in range(0,len(a[2]),3) for channel in ((255,0,0) if a[2][i:i+3]!=b[2][i:i+3] else (255,255,255)))
            png(out/(name+'-diff.png'),(w,h,diff))
            swap=rng.choice([False,True]);left,right=(b,a) if swap else (a,b)
            pair=b''.join(left[2][y*w*3:(y+1)*w*3]+b'\x80'*24+right[2][y*w*3:(y+1)*w*3] for y in range(h))
            png(out/(name+'-blind.png'),(w*2+8,h,pair));secret[name]={'left':'candidate' if swap else 'reference','right':'reference' if swap else 'candidate'}
    (out/'blind-key.json').write_text(json.dumps(secret,indent=2)+'\n')
    (out/'pixel-results.json').write_text(json.dumps(results,indent=2)+'\n')
    return results

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference-image',type=pathlib.Path,default=HERE.parent/'reference/freedos.boot.disk.720K.img')
    ap.add_argument('--qemu',default=shutil.which('qemu-system-i386'))
    ap.add_argument('--candidate',type=pathlib.Path,help='JSON argv template; browser must open {url} automatically')
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--port',type=int,default=18786,help='Fixed port keeps address-bar pixels deterministic')
    ap.add_argument('--cases',nargs='+',choices=list(CASES),default=list(CASES))
    ap.add_argument('--boot-timeout',type=float,default=30)
    ap.add_argument('--local-wait',type=float,default=6)
    ap.add_argument('--settle',type=float,default=1)
    args=ap.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    if not args.qemu:ap.error('qemu-system-i386 unavailable')
    manifest=json.loads(args.candidate.read_text()) if args.candidate else None
    if manifest and 'image' in manifest:
        p=pathlib.Path(manifest['image'])
        manifest['image']=str((args.candidate.parent/p).resolve()) if not p.is_absolute() else str(p)
    summary={'schema':1,'release_pass':False,'harness_sha256':digest(pathlib.Path(__file__)),'case_specs':{c:CASES[c] for c in args.cases},'qemu_version':subprocess.check_output([args.qemu,'--version'],text=True).splitlines()[0],'reference_image_sha256':digest(args.reference_image),'candidate_image_sha256':digest(pathlib.Path(manifest['image'])) if manifest and 'image' in manifest else None,'fixture_hashes':{str(p.relative_to(FIXTURES)):digest(p) for p in FIXTURES.rglob('*') if p.is_file()},'gif_sha256':hashlib.sha256(GIF).hexdigest(), 'reference':{},'candidate':{},'parity':'candidate_pending','strict_8088':'pending: QEMU 486 is not ISA proof','hardware':'not_tested','memory_and_timing':'not_tested','review':'pending independent blind review','unsupported_claims':['No CSS/JavaScript/TLS parity claim','No full HTML/form/GIF/error coverage claim','No HP hardware access']}
    server=FixtureServer(args.port)
    try:
        for lane in (['reference','candidate'] if manifest else ['reference']):
            for case in args.cases:
                r=run_case(args,lane,case,server,manifest);summary[lane][case]=r
                print(f'{lane}/{case}: {r["status"]}, missing requests={r["missing_requests"]}',flush=True)
        summary['reference_pass']=all(r['functional_pass'] for r in summary['reference'].values())
        if manifest:
            comparisons=make_comparison(args,summary['reference'],summary['candidate'])
            traces={case:summary['reference'][case]['requests']==summary['candidate'][case]['requests'] for case in args.cases}
            summary['request_trace_parity']=traces
            passed=summary['reference_pass'] and all(r['functional_pass'] for r in summary['candidate'].values()) and all(traces.values()) and bool(comparisons) and all(r['pass'] for r in comparisons)
            summary['parity']='measured_fixture_parity_passed' if passed else 'failed'
        elif not summary['reference_pass']:summary['parity']='reference_failed'
    finally:
        server.close();(args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Overall:',summary['parity'])
    return 2 if summary['parity']=='candidate_pending' else (0 if summary['parity']=='measured_fixture_parity_passed' else 1)

if __name__=='__main__':raise SystemExit(main())
