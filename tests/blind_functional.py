#!/usr/bin/env python3
"""Build an anonymous, reproducible functional-review packet from parity evidence.

No emulator/browser is started. The private key must remain outside the review
folder. All available cases and recorded requests are included, including failed
or missing captures. Screenshots retain exact CGA pixels except a disclosed,
symmetric title-row mask. Fixture response bytes are checked before redaction.
"""
import argparse
import hashlib
import json
import pathlib
import random
import re
import secrets
import urllib.parse
import parity

LANES=('reference','candidate')
BRANDS=re.compile(r'ELKSWeb|MicroWeb',re.I)
KEY_NAMES={'return':'Enter','ret':'Enter','spc':'Space','tab':'Tab','up':'Up','down':'Down',
           'end':'End','home':'Home','backspace':'Backspace','ctrl-l':'Ctrl+L'}
PRIORITY=('navigation','forms','radio_action','anchors','textarea_action','select_action',
          'entities_link','entities_form','charset','relative_redirect','auto_columns',
          'tablewidth','post_edit_checkbox','field_limits','large')


def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n')
def clean(text):return BRANDS.sub('[browser name withheld]',str(text))


def resolve_evidence(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root):raise ValueError('Evidence path escapes run directory')
    return path


def reconstruct_response(record,fixtures,url):
    """Reconstruct known fixture responses; hashes reject changed/unknown sources."""
    path=record['path'].split('?',1)[0]
    method=record.get('method','GET')
    wire=None
    headers={}
    if method=='POST':
        data=record.get('request_body','').encode('ascii')
        body=b'<html><title>POST submitted</title><body><h1>Form received</h1><p>'+data+b'</p></body></html>'
        kind='text/html'
    elif record.get('injected_fault')=='truncated_body':
        body=b'Injected truncated fixture';kind='text/html'
        wire=b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 999\r\n\r\n'+body
    elif path in ('/chunked','/truncated','/malformed'):
        body=b'<html><title>Framing fixture</title><body><h1>Framed body</h1></body></html>';kind='text/html'
        if path=='/chunked':
            wire=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n'+('%x\r\n'%len(body)).encode()+body+b'\r\n0\r\n\r\n'
        elif path=='/truncated':wire=b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 999\r\n\r\n'+body
        else:wire=b'INVALID STATUS\r\n\r\n'+body
    elif path in ('/redirect','/relative-redirect','/loop'):
        body=b'Redirect';kind='text/plain'
        origin=urllib.parse.urlsplit(url)
        headers['Location']=('/next.htm' if path=='/relative-redirect' else
                             f'{origin.scheme}://{origin.netloc}'+('/loop' if path=='/loop' else '/next.htm'))
    elif path=='/charset.htm':
        body=b'<html><title>Legacy charset</title><body><h1>caf\xe9 \x93quote\x94 \x80</h1><p>Cr\xe8me br\xfbl\xe9e</p><form action="/submit"><input name="q" value="caf\xe9"><input type="submit" value="Send"></form></body></html>'
        kind='text/html; charset=windows-1252'
    elif path=='/literal.txt':
        body=b'<h1>Literal markup</h1> &amp; remains literal\nWi.!    spaced\n1234\tcolumn\nLast line';kind='text/plain'
    elif path=='/download.bin':body=bytes(range(256))*16+b'ELKSWEB-END\0';kind='application/octet-stream'
    elif path=='/download-large.bin':body=(bytes(range(256))*782)[:200000];kind='application/octet-stream'
    elif path=='/large.htm':
        body=b'<html><title>Resource fixture</title><body><h1>Resource boundary</h1>'+b'<p>Repeated bounded fixture line.</p>'*2000+b'<p>END MARKER</p></body></html>';kind='text/html'
    elif path=='http://fixture.invalid/proxy.htm':
        body=b'<html><title>Proxy fixture</title><body><h1>Proxy reached</h1></body></html>';kind='text/html'
    elif path=='/submit':body=b'<html><title>Submitted</title><body>Form received</body></html>';kind='text/html'
    elif path.startswith('/') and (fixtures/path[1:]).is_file() and '/' not in path[1:]:
        body=(fixtures/path[1:]).read_bytes()
        kind='image/gif' if path.endswith('.gif') else 'image/png' if path.endswith('.png') else 'text/html'
    else:
        body=b'<html><title>Missing fixture</title><body><h1>404 fixture</h1></body></html>';kind='text/html'
    if sha(body)!=record.get('body_sha256'):
        raise ValueError('Fixture body changed or reconstruction unavailable: '+record['path'])
    if record.get('wire_sha256') and (wire is None or sha(wire)!=record['wire_sha256']):
        raise ValueError('Wire fixture changed: '+record['path'])
    headers={'Content-Type':kind,'Content-Length':len(body),**headers}
    if wire:headers={'raw_wire_is_authoritative':True}
    return body,headers,wire


def trace_equal(a,b):
    return a.get('requests',[])==b.get('requests',[])


def ordered_cases(summary):
    available=sorted(set(summary['case_specs'])|set(summary.get('reference',{}))|set(summary.get('candidate',{})))
    rank={name:i for i,name in enumerate(PRIORITY)}
    ordered=sorted(available,key=lambda name:(rank.get(name,999),name))
    groups=[[],[]]
    for name in ordered:
        same=trace_equal(summary.get('reference',{}).get(name,{}),summary.get('candidate',{}).get(name,{}))
        groups[bool(same)].append(name)
    result=[]
    while any(groups):
        for group in (groups[1],groups[0]):
            if group:result.append(group.pop(0))
    return result


def neutral_trace(records):
    # Preserve every logged field; reject metadata rather than silently dropping it.
    allowed={'method','path','status','body_sha256','request_body','wire_sha256','injected_fault'}
    for record in records:
        if set(record)-allowed:raise ValueError('Unrecognized trace fields: '+str(set(record)-allowed))
        if BRANDS.search(json.dumps(record)):raise ValueError('Identifying text in request trace; explicit review needed')
    return records


def screenshot(root,capture,title_visible):
    if not capture:return None
    source=resolve_evidence(root,capture['ppm'])
    pic=parity.normalize(parity.read_ppm(source.read_bytes()))
    if sha(pic[2])!=capture.get('sha256'):raise ValueError('Capture checksum mismatch: '+str(source))
    w,h,pixels=pic
    if title_visible:pixels=b'\x80'*(w*8*3)+pixels[w*8*3:]
    return w,h,pixels


def fixture_note(target,record,fixtures,url,index,private):
    body,headers,wire=reconstruct_response(record,fixtures,url)
    private.append({'path':record['path'],'body_sha256':sha(body),'bytes':len(body)})
    descriptor={'request':record['method']+' '+record['path'],'response_status':record['status'],
                'headers':headers,'headers_basis':'Reconstructed fixture-server behavior; response headers were not logged unless raw wire is provided.',
                'response_body_bytes':len(body),'body_sha256_before_redaction':sha(body)}
    if wire is not None:
        name=f'response-{index:02d}-wire.txt'
        (target/name).write_text(wire.decode('latin-1'))
        descriptor['wire_file']=name
        descriptor['wire_representation']='Exact wire octets interpreted as Latin-1 text; save encoded as Latin-1 to reconstruct.'
    if headers.get('Content-Type','').startswith(('text/','application/xhtml')) or wire:
        charset='cp1252' if 'windows-1252' in headers.get('Content-Type','') else 'utf-8'
        text=body.decode(charset,errors='strict')
        redacted=clean(text)
        name=f'response-{index:02d}-body.txt'
        (target/name).write_text(redacted)
        descriptor.update(body_file=name,body_source_encoding=charset,
                          identifying_name_redacted=redacted!=text,
                          body_note='Exact decoded fixture body except explicitly disclosed browser-name redaction; HTML tags/attributes/actions unchanged.')
        if charset!='utf-8':descriptor['byte_escape_body']=''.join(chr(b) if 32<=b<127 else f'\\x{b:02x}' for b in body)
    else:
        descriptor['binary_description']=('4108 bytes: byte values 0..255 repeated 16 times, then a 12-byte application-labelled sentinel ending in NUL; sentinel label withheld.'
                                          if record['path']=='/download.bin' else
                                          'Binary fixture; exact body length and digest are retained. No browser identity-bearing binary is copied into the review packet.')
    return descriptor


def build(summary_path,fixtures,output,key_path,seed):
    root=summary_path.resolve().parent
    summary=json.loads(summary_path.read_text())
    output=output.resolve();key_path=key_path.resolve()
    if key_path.is_relative_to(output):raise ValueError('Private identity key must be outside review folder')
    if output.exists() or key_path.exists():raise ValueError('Output folder/key already exists; refusing overwrite')
    cases=ordered_cases(summary)
    rng=random.Random(seed)
    sides=[0]*(len(cases)//2)+[1]*(len(cases)-len(cases)//2);rng.shuffle(sides)
    # All available cases are retained; relative order mixes equal and unequal traces.
    private={'schema':1,'seed':seed,'source_summary':str(summary_path.resolve()),
             'source_summary_sha256':sha(summary_path.read_bytes()),'cases':{},'generator_sha256':sha(pathlib.Path(__file__).read_bytes())}
    output.mkdir(parents=True)
    index=['# Anonymous browser functional review','',
           'LEFT and RIGHT are stable within each case, but may switch identities between cases. Judge only the supplied evidence and record LEFT / RIGHT / TIE / INCONCLUSIVE before identity disclosure.',
           '', 'All available cases are included; matching and differing traces are interleaved. Neither side is presumed correct. A matching trace does not prove correct display, editing, timing, resource use, or complete content. A differing trace is not automatically a defect.',
           '', 'The traces are the complete server records retained by the run, including order, repeats, request bodies and response hashes. Raw HTTP request headers, exact wire request bytes, per-key timestamps, and unrecorded actions were not captured. The records cannot establish those facts.',
           '', 'Screenshots preserve 640×200 pixels except the top 8 title rows, symmetrically greyed while browser bars are visible. This removes direct application-title identifiers. Document pixels remain intact when bars are hidden. Shared fixture titles containing application names are explicitly redacted in decoded body excerpts. No other response content or trace entry is suppressed. Distinctive UI behavior may still suggest identity; perfect blinding is not guaranteed.',
           '', 'Do not treat an absent screenshot, an unfinished load, or a missing request as success. Explain the visible failure or mark it inconclusive. Review navigation reachability, submitted names/values, editing effects, selection state, error handling, and readable/clickable layout separately.', '', '## Cases','']
    coverage={'total_cases':len(cases),'included_cases':cases,'omitted_cases':[],
              'same_recorded_trace_cases':0,'different_recorded_trace_cases':0,'missing_lane_cases':[],
              'failed_or_incomplete_capture_sides':[],'missing_screenshots':[],'screenshot_title_mask':[0,0,640,8]}
    for number,(case,side) in enumerate(zip(cases,sides),1):
        case_id=f'case-{number:02d}'
        directory=output/case_id;directory.mkdir()
        lanes=(LANES[side],LANES[1-side]);spec=summary['case_specs'].get(case,{})
        result={label:summary.get(lane,{}).get(case,{}) for label,lane in zip(('LEFT','RIGHT'),lanes)}
        private['cases'][case_id]={'case':case,'LEFT':lanes[0],'RIGHT':lanes[1],'fixtures':[],
                                  'private_errors':{label:result[label].get('error') for label in ('LEFT','RIGHT')}}
        same=trace_equal(result['LEFT'],result['RIGHT'])
        coverage['same_recorded_trace_cases' if same else 'different_recorded_trace_cases']+=1
        if not all(result.values()):coverage['missing_lane_cases'].append(case_id)
        page=[f'# {case_id}: {case}','',f'Open `{spec.get("path","unrecorded")}`.',
              '', '## Actions and captures','', '| Step | Action | State | Screenshots |','|---|---|---|---|']
        descriptions=[];seen=set()
        for label in ('LEFT','RIGHT'):
            r=result[label];records=neutral_trace(r.get('requests',[]))
            dump(directory/(label.lower()+'-trace.json'),records)
            if r.get('status')!='captured':coverage['failed_or_incomplete_capture_sides'].append({'case':case_id,'side':label,'status':r.get('status','absent')})
            for record in records:
                signature=json.dumps(record,sort_keys=True)
                if signature in seen:continue
                seen.add(signature)
                descriptions.append(fixture_note(directory,record,fixtures,r.get('url',''),len(descriptions)+1,private['cases'][case_id]['fixtures']))
        if case=='local':
            body=(fixtures/'local.htm').read_bytes()
            if sha(body)!=summary.get('fixture_hashes',{}).get('local.htm'):raise ValueError('Local fixture checksum mismatch')
            (directory/'local-body.txt').write_text(clean(body.decode()))
            descriptions.append({'local_body_file':'local-body.txt','sha256_before_redaction':sha(body)})
        dump(directory/'responses.json',descriptions)
        defined_states={state for state,key in spec.get('steps',[])}
        for label in ('LEFT','RIGHT'):
            unexpected=set(result[label].get('captures',{}))-defined_states
            if unexpected:raise ValueError('Unspecified captures would be omitted: '+str(unexpected))
        visible=True;states=[]
        for step,(state,key) in enumerate(spec.get('steps',[])):
            if key=='f3':visible=not visible
            pictures=[screenshot(root,result[label].get('captures',{}).get(state),visible) for label in ('LEFT','RIGHT')]
            links=[]
            for label,pic in zip(('LEFT','RIGHT'),pictures):
                if pic:
                    name=f'{step:02d}-{state}-{label.lower()}.png';parity.png(directory/name,pic);links.append(f'[{label}]({name})')
                else:links.append(label+': MISSING')
            if all(pictures):
                w,h= pictures[0][:2]
                if pictures[1][:2]!=(w,h):raise ValueError('Screenshot pair geometry mismatch')
                joined=b''.join(pictures[0][2][y*w*3:(y+1)*w*3]+b'\x80'*24+pictures[1][2][y*w*3:(y+1)*w*3] for y in range(h))
                name=f'{step:02d}-{state}-pair.png';parity.png(directory/name,(2*w+8,h,joined));links.append(f'[PAIR: LEFT then RIGHT]({name})')
            action='Capture after initial load' if key is None else 'Press '+KEY_NAMES.get(key,key.upper() if len(key)>1 else key)
            page.append(f'| {step} | {action} | {state} | '+', '.join(links)+' |')
            missing=[label for label,pic in zip(('LEFT','RIGHT'),pictures) if pic is None]
            states.append({'state':state,'key':key,'missing_sides':missing})
            if missing:coverage['missing_screenshots'].append({'case':case_id,'state':state,'sides':missing})
        page+=['','The action sequence is exact as recorded in the saved case specification. Capture names alone do not prove the requested action completed. Timing is not reconstructed from a current harness. Any saved initial_wait is listed in case.json; other waits are unavailable here.',
               '', '## Full recorded request traces','', '[LEFT](left-trace.json) · [RIGHT](right-trace.json)',
               '', '## Response fixtures','', '[Response descriptions, headers and fixture body files](responses.json)',
               '', '## Reviewer verdict','', '- Navigation / reached destination:','- Form/edit/selection correctness:','- Error and incomplete-load behavior:','- Readability and accessible links/controls:','- Preferred side: LEFT / RIGHT / TIE / INCONCLUSIVE','- Evidence and remaining uncertainty:']
        public={'case':case,'path':spec.get('path'),'steps':spec.get('steps',[]),'initial_wait':spec.get('initial_wait','not preserved'),
                'required_requests':spec.get('requests',[]),'required_exact_requests':spec.get('exact_requests',[]),'states':states,
                'observed':{label:{'capture_status':result[label].get('status','absent'),
                                   'capture_error':('Capture failed; environment-specific diagnostic retained privately.' if result[label].get('error') else ''),
                                   'missing_required_requests':result[label].get('missing_requests',[]),
                                   'missing_required_exact_requests':result[label].get('missing_exact_requests',[])} for label in ('LEFT','RIGHT')}}
        dump(directory/'case.json',public)
        (directory/'README.md').write_text('\n'.join(page)+'\n')
        index.append(f'- [{case_id}: {case}]({case_id}/README.md)')
    dump(output/'coverage.json',coverage)
    index+=['','## Coverage and limits','',f'{len(cases)} cases: {coverage["same_recorded_trace_cases"]} have identical recorded traces; {coverage["different_recorded_trace_cases"]} differ. All cases in the source summary are included. Side assignments are balanced to within one case.',
            '', '[Coverage and capture omissions](coverage.json). Fixture bytes and screenshot hashes were verified against saved evidence before generating this packet. Current fixture drift causes generation to fail; it is never silently substituted.',
            '', 'This packet is a review aid for the captured scenarios, not a complete browser acceptance suite. Hardware compatibility, memory use, network timing and arbitrary-site behavior need separate evidence.']
    (output/'README.md').write_text('\n'.join(index)+'\n')
    # Fail if identifiers or serialized provenance metadata escaped into review text.
    for path in output.rglob('*'):
        if path.suffix in ('.md','.json','.txt') and BRANDS.search(path.read_text()):raise ValueError('Identity leakage in '+str(path))
    private['packet_files']={str(p.relative_to(output)):sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    key_path.parent.mkdir(parents=True,exist_ok=True);dump(key_path,private)
    key_path.chmod(0o600)
    return coverage


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--summary',type=pathlib.Path,required=True)
    ap.add_argument('--fixtures',type=pathlib.Path,default=pathlib.Path(__file__).parent/'fixtures')
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--key',type=pathlib.Path,required=True,help='Private path outside the review directory')
    ap.add_argument('--seed',help='Optional private reproducibility seed; otherwise generated and saved only in key')
    args=ap.parse_args()
    coverage=build(args.summary,args.fixtures,args.output,args.key,args.seed or secrets.token_hex(32))
    print(json.dumps({'cases':coverage['total_cases'],'identical_traces':coverage['same_recorded_trace_cases'],
                      'different_traces':coverage['different_recorded_trace_cases'],'missing_lane_cases':coverage['missing_lane_cases']},indent=2))

if __name__=='__main__':main()
