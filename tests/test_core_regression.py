"""Regression expectations for actual C core, with local raw HTTP fixtures.

Failures are bugs to fix, never automatically marked expected failures.
The library is compiled into a fresh temp directory; src/ is read-only here.
"""
import ctypes as C, os, pathlib, socket, subprocess, tempfile, threading, unittest

HERE=pathlib.Path(__file__).resolve().parent
SRC=HERE.parent/'src'
TEMP=None
LIB=None

def setUpModule():
    global TEMP, LIB
    TEMP=tempfile.TemporaryDirectory(prefix='elksweb-core-qa-')
    path=pathlib.Path(TEMP.name)/'core.dylib'
    subprocess.run(['cc','-shared','-fPIC','-g','-DEW_HOST_TEST','-I'+str(SRC),'-I'+str(HERE.parent/'font'),str(SRC/'url.c'),str(SRC/'html.c'),str(SRC/'net.c'),str(SRC/'memory.c'),str(HERE.parent/'font/font.c'),str(HERE.parent/'font/body_font.c'),str(HERE/'qa_core_shim.c'),'-o',str(path)],check=True,capture_output=True)
    LIB=C.CDLL(str(path))
    LIB.ew_resolve_url.argtypes=[C.c_char_p,C.c_char_p,C.c_void_p,C.c_uint]
    LIB.ew_parse.argtypes=[C.c_char_p,C.c_char_p]
    LIB.ew_fetch.argtypes=[C.c_char_p,C.c_void_p,C.c_uint,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p]
    LIB.ew_fetch.restype=C.c_int32
    LIB.ew_fetch_document.argtypes=[C.c_char_p,C.c_void_p,C.c_void_p,C.c_uint,C.c_char_p]
    LIB.ew_fetch_document.restype=C.c_int32
    LIB.ew_fetch_to_fd.argtypes=[C.c_char_p,C.c_int,C.c_uint32,C.c_void_p,C.c_void_p,C.c_uint]
    LIB.ew_fetch_to_fd.restype=C.c_int32
    LIB.ew_parse_source.argtypes=[C.c_char_p]
    LIB.ew_anchor_y.argtypes=[C.c_char_p]
    LIB.ew_host_is_ipv4.argtypes=[C.c_char_p]
    LIB.qa_run_data.restype=C.c_void_p
    LIB.ew_source_byte.argtypes=[C.c_uint32]
    LIB.ew_source_byte.restype=C.c_ubyte
    LIB.ew_form_url.argtypes=[C.c_uint,C.c_void_p,C.c_uint,C.c_void_p,C.c_uint]
    for name in ['qa_title','qa_link','qa_link_value','ew_select_label']:getattr(LIB,name).restype=C.c_char_p

def tearDownModule():
    if LIB:LIB.ew_source_free()
    if TEMP:TEMP.cleanup()

class OneHTTP:
    def __init__(self,response):
        self.response=response;self.request=b'';self.requests=[];self.sock=socket.socket();self.sock.bind(('127.0.0.1',0));self.sock.listen(8);self.sock.settimeout(.5)
        self.url=f'http://127.0.0.1:{self.sock.getsockname()[1]}'
        self.thread=threading.Thread(target=self.serve,daemon=True);self.thread.start()
    def serve(self):
        try:
            responses=self.response if isinstance(self.response,list) else [self.response]
            for response in responses:
                conn,_=self.sock.accept();conn.settimeout(2)
                with conn:
                    request=b''
                    while b'\r\n\r\n' not in request:
                        part=conn.recv(1024)
                        if not part:break
                        request+=part
                    headers,_,body=request.partition(b'\r\n\r\n')
                    length=0
                    for line in headers.split(b'\r\n'):
                        if line.lower().startswith(b'content-length:'):length=int(line.split(b':',1)[1])
                    while len(body)<length:
                        part=conn.recv(1024)
                        if not part:break
                        body+=part;request+=part
                    self.request=request;self.requests.append(request)
                    conn.sendall(response(self) if callable(response) else response)
        except (OSError,TimeoutError):pass
    def close(self):self.thread.join(timeout=4);self.sock.close()

class Core(unittest.TestCase):
    def setUp(self):self.old_proxy=os.environ.pop('HTTP_PROXY',None)
    def tearDown(self):
        if self.old_proxy is not None:os.environ['HTTP_PROXY']=self.old_proxy
    def resolve(self,base,ref):
        out=C.create_string_buffer(256);r=LIB.ew_resolve_url(base.encode(),ref.encode(),out,256);self.assertEqual(r,0);return out.value.decode()
    def fetch(self,response,path='/',cap=64):
        server=OneHTTP(response);out=C.create_string_buffer(max(cap,1));final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
        try:r=LIB.ew_fetch((server.url+path).encode(),out,cap,final,error,96,None)
        finally:server.close()
        return r,out.value,error.value,server.request
    def fetch_url(self,url,post=None,cap=64):
        out=C.create_string_buffer(max(cap,1));final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
        r=LIB.ew_fetch(url.encode(),out,cap,final,error,96,post)
        return r,out.value,error.value,final.value
    def runs(self):
        return [(C.string_at(LIB.qa_run_data(i),LIB.qa_run_length(i)),LIB.qa_style(i),LIB.qa_y(i)) for i in range(LIB.qa_runs()) if LIB.qa_run_kind(i)==0]
    def test_url_parent(self):self.assertEqual(self.resolve('http://host/a/b.htm','../c'),'http://host/c')
    def test_url_empty_reference_preserves_document_and_query(self):self.assertEqual(self.resolve('http://host/a/b.htm?old#frag',''),'http://host/a/b.htm?old')
    def test_url_query_replaces_fragment(self):self.assertEqual(self.resolve('http://host/a/b.htm#frag','?new'),'http://host/a/b.htm?new')
    def test_url_root_reference_without_base_path(self):self.assertEqual(self.resolve('http://host?old','/new'),'http://host/new')
    def test_url_bounds_guard(self):
        out=C.create_string_buffer(b'GUARD',6)
        self.assertEqual(LIB.ew_resolve_url(b'http://host/',b'x'*255,out,2),-1);self.assertEqual(out.raw,b'GUARD\0')
    def test_title_entities(self):
        LIB.ew_parse(b'<title>A &amp; B</title><p>Text</p>',b'http://host/a');self.assertEqual(LIB.qa_title(),b'A & B')
    def test_self_closing_break(self):
        LIB.ew_parse(b'one<br/>two',b'http://host/a');self.assertEqual(LIB.qa_runs(),2);self.assertGreater(LIB.qa_y(1),LIB.qa_y(0))
    def test_nested_bold_stays_bold(self):
        LIB.ew_parse(b'<b>outer<b>inner</b>tail</b>normal',b'http://host/a')
        runs=self.runs();self.assertEqual(b''.join(t for t,style,y in runs if style&1),b'outerinnertail');self.assertEqual(b''.join(t for t,style,y in runs if not style&1),b'normal')
    def test_table_closing_tags_cannot_overflow_layout_x(self):
        LIB.ew_parse(b'</td>'*2050+b'X',b'http://host/a');self.assertGreaterEqual(LIB.qa_x(0),0);self.assertLessEqual(LIB.qa_x(0),624)
    def test_link_limit_is_flagged(self):
        LIB.ew_parse(b'<a href="/x">x</a>'*(LIB.qa_link_limit()+1),b'http://host/a');self.assertEqual(LIB.qa_links(),LIB.qa_link_limit());self.assertTrue(LIB.qa_truncated())
    def test_text_limit_is_bounded(self):
        LIB.ew_parse(b'x '*(LIB.qa_text_limit()+1),b'http://host/a');self.assertTrue(LIB.qa_truncated());self.assertLess(LIB.qa_text_len(),LIB.qa_text_limit())
    def test_form_query_precedes_fragment(self):
        LIB.ew_parse(b'<form action="/search#part"><input name="q" value="one two"><input type="submit" value="Go"></form>',b'http://host/a')
        url=C.create_string_buffer(256);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(1,url,256,post,512),0);self.assertEqual(url.value,b'http://host/search?q=one+two#part')
    def test_content_length_body(self):self.assertEqual(self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 5\r\n\r\nhello')[:2],(5,b'hello'))
    def test_truncated_body_is_error(self):self.assertLess(self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 8\r\n\r\nshort')[0],0)
    def test_chunked_body(self):self.assertEqual(self.fetch(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhi\r\n0\r\n\r\n')[:2],(2,b'hi'))
    def test_invalid_content_length_rejected(self):self.assertLess(self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: garbage\r\n\r\nhello')[0],0)
    def test_conflicting_content_lengths_rejected(self):self.assertLess(self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 5\r\nContent-Length: 2\r\n\r\nhello')[0],0)
    def test_invalid_chunk_suffix_rejected(self):self.assertLess(self.fetch(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2NOTHEX\r\nhi\r\n0\r\n\r\n')[0],0)
    def test_request_line_injection_rejected(self):
        r,_,_,request=self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 0\r\n\r\n','/safe\r\nX-Injected: yes')
        self.assertLess(r,0);self.assertNotIn(b'X-Injected:',request)
    def test_long_url_returns_error_message(self):
        out=C.create_string_buffer(64);final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
        self.assertLess(LIB.ew_fetch(b'http://host/'+b'x'*300,out,64,final,error,96,None),0);self.assertTrue(error.value)
    def test_zero_output_capacity_rejected_without_write(self):
        with tempfile.NamedTemporaryFile() as fixture:
            fixture.write(b'abc');fixture.flush()
            out=C.create_string_buffer(b'UNCHANGED',64);before=out.raw;final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
            r=LIB.ew_fetch(fixture.name.encode(),out,0,final,error,96,None)
            self.assertLess(r,0);self.assertEqual(out.raw,before)
    def test_local_truncation_is_bounded_and_flagged(self):
        with tempfile.NamedTemporaryFile() as fixture:
            fixture.write(b'abcdef');fixture.flush()
            out=C.create_string_buffer(4);final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
            self.assertEqual(LIB.ew_fetch(fixture.name.encode(),out,4,final,error,96,None),3)
            self.assertEqual(out.value,b'abc');self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,1)
    def test_http_post_body_and_length(self):
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok')
        try:result=self.fetch_url(server.url+'/submit',b'q=one+two&opt=yes')
        finally:server.close()
        self.assertEqual(result[:2],(2,b'ok'));self.assertIn(b'POST /submit HTTP/1.0\r\n',server.request)
        self.assertIn(b'Content-Length: 17\r\n',server.request);self.assertTrue(server.request.endswith(b'q=one+two&opt=yes'))
    def test_proxy_absolute_target_and_origin_host(self):
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok')
        os.environ['HTTP_PROXY']=server.url
        try:result=self.fetch_url('http://fixture.invalid/path?q=x')
        finally:server.close();os.environ.pop('HTTP_PROXY',None)
        self.assertEqual(result[:2],(2,b'ok'));self.assertIn(b'GET http://fixture.invalid/path?q=x HTTP/1.0',server.request);self.assertIn(b'Host: fixture.invalid\r\n',server.request)
    def test_relative_redirect_resolves(self):
        responses=[b'HTTP/1.0 302 Found\r\nLocation: ../end\r\nContent-Length: 0\r\n\r\n',b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok']
        server=OneHTTP(responses)
        try:result=self.fetch_url(server.url+'/dir/start')
        finally:server.close()
        self.assertEqual(result[:2],(2,b'ok'));self.assertTrue(result[3].endswith(b'/end'));self.assertEqual(len(server.requests),2)
    def test_redirect_loop_bounded(self):
        response=b'HTTP/1.0 302 Found\r\nLocation: /loop\r\nContent-Length: 0\r\n\r\n'
        server=OneHTTP([response]*6)
        try:result=self.fetch_url(server.url+'/loop')
        finally:server.close()
        self.assertLess(result[0],0);self.assertIn(b'redirect',result[2].lower());self.assertLessEqual(len(server.requests),6)
    def test_post_307_redirect_preserves_method_and_body(self):
        server=OneHTTP([b'HTTP/1.0 307 Temporary Redirect\r\nLocation: /again\r\nContent-Length: 0\r\n\r\n',b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok'])
        try:result=self.fetch_url(server.url+'/submit',b'q=test')
        finally:server.close()
        self.assertEqual(result[:2],(2,b'ok'));self.assertIn(b'POST /again HTTP/1.0',server.requests[1]);self.assertTrue(server.requests[1].endswith(b'q=test'))
    def test_chunk_extensions_valid(self):self.assertEqual(self.fetch(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2;name=value\r\nhi\r\n0\r\n\r\n')[:2],(2,b'hi'))
    def test_missing_chunk_crlf_is_error(self):self.assertLess(self.fetch(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhiXX0\r\n\r\n')[0],0)
    def test_truncated_chunk_is_error(self):self.assertLess(self.fetch(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhi')[0],0)
    def test_http_body_truncation_flag(self):
        result=self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 6\r\n\r\nabcdef',cap=4)
        self.assertEqual(result[:2],(3,b'abc'));self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,1)
    def test_overlong_header_rejected(self):self.assertLess(self.fetch(b'HTTP/1.0 200 OK\r\nX: '+b'a'*(LIB.qa_url_limit()*4)+b'\r\n\r\n')[0],0)
    def test_checkbox_successful_controls(self):
        LIB.ew_parse(b'<form action="/go" method="post"><input name="text" value="one two"><input type="checkbox" name="yes" value="Y" checked><input type="checkbox" name="no" value="N"><input type="submit" name="send" value="Go"></form>',b'http://host/')
        url=C.create_string_buffer(256);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(3,url,256,post,512),0);self.assertEqual(post.value,b'text=one+two&yes=Y&send=Go')
    def test_form_encoding_exact_capacity(self):
        LIB.ew_parse(b'<form action="/go" method="post"><input name="q" value="x"><input type="submit"></form>',b'http://host/')
        url=C.create_string_buffer(256);post=C.create_string_buffer(4)
        self.assertEqual(LIB.ew_form_url(1,url,256,post,4),0);self.assertEqual(post.value,b'q=x')
    def test_proxy_omits_fragment_from_request_target(self):
        server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok');os.environ['HTTP_PROXY']=server.url
        try:result=self.fetch_url('http://fixture.invalid/path#private')
        finally:server.close();os.environ.pop('HTTP_PROXY',None)
        self.assertEqual(result[:2],(2,b'ok'));self.assertIn(b'GET http://fixture.invalid/path HTTP/1.0',server.request);self.assertNotIn(b'#private',server.request)
    def test_malformed_status_code_rejected(self):self.assertLess(self.fetch(b'HTTP/1.0 200garbage\r\nContent-Length: 0\r\n\r\n')[0],0)
    def test_table_layout_never_moves_runs_negative(self):
        LIB.ew_parse((HERE/'fixtures/layout-negative.htm').read_bytes(),b'http://host/')
        for i in range(LIB.qa_runs()):self.assertGreaterEqual(LIB.qa_x(i),0)
    def test_ipv4_classification_accepts_only_dotted_quad(self):
        for host in [b'0.0.0.0',b'127.0.0.1',b'255.255.255.255',b'10.0.2.2']:
            with self.subTest(host=host):self.assertTrue(LIB.ew_host_is_ipv4(host))
        for host in [b'68k.news',b'3com.com',b'256.1.2.3',b'1.2.3',b'1.2.3.4.5',b'1..2.3',b'1.2.3.x',b'1.2.3.4 ',b'',b'1234']:
            with self.subTest(host=host):self.assertFalse(LIB.ew_host_is_ipv4(host))
    def test_large_local_lengths_and_truncation(self):
        for size in [40000,59999,60000]:
            with self.subTest(size=size),tempfile.NamedTemporaryFile() as fixture:
                fixture.write(b'x'*size);fixture.flush();out=C.create_string_buffer(60000);final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
                n=LIB.ew_fetch(fixture.name.encode(),out,60000,final,error,96,None)
                self.assertEqual(n,min(size,59999));self.assertEqual(len(out.value),min(size,59999));self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,int(size>=60000))
    def test_large_http_lengths_and_truncation(self):
        for size in [40000,59999,60000]:
            with self.subTest(size=size):
                result=self.fetch(b'HTTP/1.0 200 OK\r\nContent-Length: '+str(size).encode()+b'\r\n\r\n'+b'x'*size,cap=60000)
                self.assertEqual(result[0],min(size,59999));self.assertEqual(len(result[1]),min(size,59999));self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,int(size>=60000))
    def test_long_comment_tail_still_parsed(self):
        LIB.ew_parse(b'<!--'+b'x'*40000+b'--><title>Tail title</title><p>Tail text</p>',b'http://host/')
        self.assertEqual(LIB.qa_title(),b'Tail title');self.assertGreater(LIB.qa_text_len(),0);self.assertFalse(LIB.qa_truncated())
    def test_source_storage_lifecycle(self):
        LIB.ew_source_free();self.assertFalse(C.c_void_p.in_dll(LIB,'ew_source').value)
        self.assertEqual(LIB.ew_source_init(),0);p=C.c_void_p.in_dll(LIB,'ew_source').value;self.assertTrue(p)
        self.assertEqual(LIB.ew_source_init(),0);self.assertEqual(C.c_void_p.in_dll(LIB,'ew_source').value,p)
        C.memset(p,ord('z'),60000);self.assertEqual(C.string_at(p+59999,1),b'z')
        LIB.ew_source_free();LIB.ew_source_free();self.assertFalse(C.c_void_p.in_dll(LIB,'ew_source').value)
    def test_long_link_does_not_hide_following_page_text(self):
        LIB.ew_parse(b'<a href="/'+b'x'*500+b'">Headline</a><p>Following article text</p>',b'http://host/')
        self.assertGreater(LIB.qa_text_len(),len('Headline'))
    def test_nested_italic_retains_style(self):
        LIB.ew_parse(b'<i>outer<em>inner</em>tail</i>normal',b'http://host/')
        runs=self.runs();self.assertEqual(b''.join(t for t,style,y in runs if style&16),b'outerinnertail');self.assertEqual(b''.join(t for t,style,y in runs if not style&16),b'normal')
    def test_pre_whitespace_cannot_overflow_coordinates(self):
        LIB.ew_parse(b'<pre>'+b' '*5000+b'tail</pre>',b'http://host/')
        self.assertGreater(LIB.qa_runs(),0)
        for i in range(LIB.qa_runs()):self.assertGreaterEqual(LIB.qa_x(i),0);self.assertLessEqual(LIB.qa_x(i),624)
    def test_long_link_preserves_full_url(self):
        href=b'/'+b'x'*500;LIB.ew_parse(b'<a href="'+href+b'">Headline</a>',b'http://host/')
        self.assertEqual(LIB.qa_link(0),b'http://host'+href)
    def test_256th_link_keeps_nonzero_run_reference(self):
        LIB.ew_parse(b'<a href="/x">x</a>'*LIB.qa_link_limit(),b'http://host/')
        self.assertEqual(LIB.qa_links(),LIB.qa_link_limit());self.assertEqual(LIB.qa_run_link(LIB.qa_runs()-1),LIB.qa_link_limit())
    def test_field_storage_preserves_full_declared_lengths(self):
        name=b'n'*31;value=b'v'*79
        LIB.ew_parse(b'<form action="/go" method="post"><input name="'+name+b'" value="'+value+b'"><input type="submit"></form>',b'http://host/')
        url=C.create_string_buffer(1024);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(1,url,1024,post,512),0);self.assertEqual(post.value,name+b'='+value)
    def test_segmented_local_comment_and_tag_crossing(self):
        for padding in [59988,90000]:
            with self.subTest(padding=padding),tempfile.NamedTemporaryFile() as fixture:
                html=b'<!--'+b'x'*padding+b'--><title>Across banks</title><p>Visible tail</p>'
                fixture.write(html);fixture.flush();final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
                self.assertEqual(LIB.ew_fetch_document(fixture.name.encode(),final,error,96,None),len(html))
                self.assertEqual(C.c_uint32.in_dll(LIB,'ew_source_length').value,len(html))
                LIB.ew_parse_source(b'http://host/');self.assertEqual(LIB.qa_title(),b'Across banks');self.assertGreater(LIB.qa_text_len(),0);self.assertFalse(LIB.qa_truncated())
    def test_segmented_http_lengths_and_truncation(self):
        for size in [90000,119999,120000]:
            with self.subTest(size=size):
                server=OneHTTP(b'HTTP/1.0 200 OK\r\nContent-Length: '+str(size).encode()+b'\r\n\r\n'+b'x'*size)
                final=C.create_string_buffer(1024);error=C.create_string_buffer(96)
                try:n=LIB.ew_fetch_document((server.url+'/large').encode(),final,error,96,None)
                finally:server.close()
                self.assertEqual(n,min(size,119999));self.assertEqual(C.c_uint32.in_dll(LIB,'ew_source_length').value,min(size,119999));self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,int(size>=120000))

    def test_merged_words_preserve_single_spaces(self):
        LIB.ew_parse(b'alpha   beta\n gamma',b'http://host/')
        self.assertEqual(self.runs()[0][0],b'alpha beta gamma')
    def test_merged_text_wrap_preserves_word_order(self):
        words=[('word%03d'%i).encode() for i in range(150)]
        LIB.ew_parse(b' '.join(words),b'http://host/')
        runs=self.runs();self.assertEqual(b' '.join(t for t,style,y in runs).split(),words)
        self.assertGreater(len(set(y for t,style,y in runs)),1)
        self.assertFalse(LIB.qa_truncated())
    def test_long_word_buffer_fragments_preserve_every_character(self):
        word=b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'*20
        LIB.ew_parse(word,b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),word)
        self.assertFalse(LIB.qa_truncated())

    def test_embedded_scheme_in_relative_reference_is_not_absolute(self):
        for ref,expected in [
            ('article.php?a=https://news.google.com/rss/ABC?oc=5','http://68k.news/article.php?a=https://news.google.com/rss/ABC?oc=5'),
            ('/article?a=https://host/x','http://68k.news/article?a=https://host/x'),
            ('?a=https://host/x','http://68k.news/?a=https://host/x'),
            ('#https://host/x','http://68k.news/#https://host/x')]:
            with self.subTest(ref=ref):self.assertEqual(self.resolve('http://68k.news/',ref),expected)
    def test_document_nonredirect_location_preserves_body(self):
        for status in (200,201):
            with self.subTest(status=status):
                body=b'<p>Original body</p>'
                response=('HTTP/1.0 %d OK\r\nLocation: /wrong\r\nContent-Length: %d\r\n\r\n'%(status,len(body))).encode()+body
                server=OneHTTP(response);final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
                try:n=LIB.ew_fetch_document((server.url+'/original').encode(),final,error,128,None)
                finally:server.close()
                self.assertEqual(n,len(body));self.assertEqual(final.value,(server.url+'/original').encode())
                self.assertEqual(bytes(LIB.ew_source_byte(i) for i in range(n)),body);self.assertEqual(len(server.requests),1)
    def test_document_redirect_discards_intermediate_body(self):
        body=b'<p>Final body</p>'
        server=OneHTTP([b'HTTP/1.0 302 Found\r\nLocation: /final\r\nContent-Length: 5\r\n\r\nWRONG',b'HTTP/1.0 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body])
        final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
        try:n=LIB.ew_fetch_document((server.url+'/original').encode(),final,error,128,None)
        finally:server.close()
        self.assertEqual(n,len(body));self.assertEqual(bytes(LIB.ew_source_byte(i) for i in range(n)),body)
        self.assertEqual(final.value,(server.url+'/final').encode());self.assertEqual(len(server.requests),2)

    def test_nested_small_scope_restores_regular_text(self):
        LIB.ew_parse(b'<small>outer<small>inner</small>tail</small>normal',b'http://host/')
        flag=LIB.qa_small_style();runs=self.runs()
        self.assertEqual(b''.join(t for t,style,y in runs if style&flag),b'outerinnertail')
        self.assertEqual(b''.join(t for t,style,y in runs if not style&flag),b'normal')
    def test_heading_bold_survives_nested_bold_close(self):
        LIB.ew_parse(b'<h1><b>First</b> tail</h1>normal',b'http://host/')
        runs=self.runs();self.assertEqual(b''.join(t for t,style,y in runs if style&1),b'First tail')
        self.assertEqual(b''.join(t for t,style,y in runs if not style&1),b'normal')
    def test_center_scope_positions_line_and_restores_left_margin(self):
        LIB.ew_parse(b'<center>Centered</center>Left',b'http://host/')
        self.assertEqual(LIB.qa_runs(),2);self.assertGreater(LIB.qa_x(0),100)
        self.assertEqual(LIB.qa_x(1),0);self.assertGreater(LIB.qa_y(1),LIB.qa_y(0))
    def test_nested_center_and_wrapping_stay_in_viewport(self):
        LIB.ew_parse(b'<center>Outer<center>Inner</center>'+b'long centered text '*100+b'</center>Left',b'http://host/')
        for i in range(LIB.qa_runs()):self.assertGreaterEqual(LIB.qa_x(i),0);self.assertLess(LIB.qa_x(i),624)
        self.assertEqual(LIB.qa_x(LIB.qa_runs()-1),0)

    def test_binary_fd_fetch_writes_exact_body_without_terminator(self):
        for body,status in [(b'A\x00B\xff',200),(b'',204)]:
            with self.subTest(status=status):
                response=('HTTP/1.0 %d OK\r\nContent-Length: %d\r\n\r\n'%(status,len(body))).encode()+body
                server=OneHTTP(response);final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
                with tempfile.TemporaryFile() as output:
                    try:n=LIB.ew_fetch_to_fd((server.url+'/binary').encode(),output.fileno(),60000,final,error,128)
                    finally:server.close()
                    self.assertEqual(n,len(body));self.assertEqual(os.fstat(output.fileno()).st_size,len(body));output.seek(0);self.assertEqual(output.read(),body)
    def test_binary_fd_redirect_has_only_final_body(self):
        body=b'GIF\x00DATA';server=OneHTTP([b'HTTP/1.0 302 Found\r\nLocation: /final\r\nContent-Length: 5\r\n\r\nWRONG',b'HTTP/1.0 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body])
        final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
        with tempfile.TemporaryFile() as output:
            try:n=LIB.ew_fetch_to_fd((server.url+'/original').encode(),output.fileno(),60000,final,error,128)
            finally:server.close()
            self.assertEqual(n,len(body));output.seek(0);self.assertEqual(output.read(),body)

    def test_href_amp_entity_decoded_before_url_resolution(self):
        LIB.ew_parse(b'<a href="/next?a=one&amp;b=two">Open</a>',b'http://host/')
        self.assertEqual(LIB.qa_link(0),b'http://host/next?a=one&b=two')
    def test_form_attribute_entities_decoded_then_safely_encoded(self):
        LIB.ew_parse(b'<form action="/submit" method="post"><input name="q" value="A&amp;B &quot;Q&quot;"><input type="submit"></form>',b'http://host/')
        url=C.create_string_buffer(1024);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(1,url,1024,post,512),0)
        self.assertEqual(post.value,b'q=A%26B+%22Q%22')

    def test_unknown_href_entities_preserve_literal_text(self):
        LIB.ew_parse(b'<a href="/a?x=1&foo=2&unknown;">Open</a>',b'http://host/')
        self.assertEqual(LIB.qa_link(0),b'http://host/a?x=1&foo=2&unknown;')
    def test_numeric_form_entities_encode_utf8(self):
        LIB.ew_parse(b'<form action="/go" method="post"><input name="q" value="&#65; &#x42; &#233; &apos;"><input type="submit"></form>',b'http://host/')
        url=C.create_string_buffer(1024);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(1,url,1024,post,512),0);self.assertEqual(post.value,b'q=A+B+%C3%A9+%27')
    def test_literal_utf8_punctuation_transliterates_consistently(self):
        LIB.ew_parse('‘one’ “two” — – …'.encode(),b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b"'one' \"two\" - - ...")
    def test_numeric_punctuation_matches_literal_utf8(self):
        LIB.ew_parse(b'&#8217; &#x2014; &#8230;',b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b"' - ...")
    def test_invalid_unicode_scalars_do_not_wrap_to_ascii(self):
        LIB.ew_parse(b'&#xD800; &#x110000; &#65536;',b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b'? ? ?')
    def test_unterminated_quoted_href_is_not_partially_accepted(self):
        LIB.ew_parse(b'<a href="/incomplete>Hidden link</a> Tail',b'http://host/')
        self.assertEqual(LIB.qa_links(),0)

    def form_body(self,index):
        url=C.create_string_buffer(1024);post=C.create_string_buffer(512)
        self.assertEqual(LIB.ew_form_url(index,url,1024,post,512),0)
        return post.value
    def test_password_value_serializes_without_masking_data(self):
        LIB.ew_parse(b'<form method="post"><input type="password" name="p" value="secret"><input type="submit"></form>',b'http://host/')
        self.assertEqual(LIB.qa_link_kind(0),8);self.assertEqual(self.form_body(1),b'p=secret')
    def test_radio_choose_is_exclusive_within_form_and_name(self):
        LIB.ew_parse(b'<form method="post"><input type="radio" name="a" value="one" checked><input type="radio" name="a" value="two"><input type="radio" name="b" value="other" checked><input type="submit"></form><form><input type="radio" name="a" value="external" checked></form>',b'http://host/')
        self.assertEqual(LIB.ew_radio_choose(1),0)
        self.assertEqual([LIB.qa_link_checked(i) for i in (0,1,2,4)],[0,1,1,1])
        self.assertEqual(self.form_body(3),b'a=two&b=other')
    def test_radio_default_without_value_is_on(self):
        LIB.ew_parse(b'<form method="post"><input type="radio" name="a" checked><input type="radio" name="a" value="b"><input type="submit"></form>',b'http://host/')
        self.assertEqual(self.form_body(2),b'a=on')
    def test_select_uses_selected_value_instead_of_label(self):
        LIB.ew_parse(b'<form method="post"><select name="s"><option value="one">One</option><option value="two" selected>Two</option></select><input type="submit"></form>',b'http://host/')
        self.assertEqual(LIB.ew_select_count(0),2);self.assertEqual(LIB.ew_select_index(0),1)
        self.assertEqual(LIB.ew_select_label(0,1),b'Two');self.assertEqual(LIB.qa_link_value(0),b'Two')
        self.assertEqual(self.form_body(1),b's=two');self.assertEqual(LIB.ew_select_choose(0,0),0);self.assertEqual(self.form_body(1),b's=one')
    def test_select_first_option_default_and_missing_value(self):
        LIB.ew_parse(b'<form method="post"><select name="s"><option> First label </option><option>Second</option></select><input type="submit"></form>',b'http://host/')
        self.assertEqual(LIB.ew_select_index(0),0);self.assertEqual(self.form_body(1),b's=First+label')
    def test_select_explicit_empty_value_is_preserved(self):
        LIB.ew_parse(b'<form method="post"><select name="s"><option value="">Visible label</option></select><input type="submit"></form>',b'http://host/')
        self.assertEqual(self.form_body(1),b's=')
    def test_empty_select_is_not_successful_control(self):
        LIB.ew_parse(b'<form method="post"><select name="s"></select><input name="q" value="ok"><input type="submit"></form>',b'http://host/')
        self.assertEqual(self.form_body(2),b'q=ok')
    def test_select_option_entities_decode(self):
        LIB.ew_parse(b'<form method="post"><select name="s"><option value="A&amp;B">One &amp; two</option></select><input type="submit"></form>',b'http://host/')
        self.assertEqual(LIB.ew_select_label(0,0),b'One & two');self.assertEqual(self.form_body(1),b's=A%26B')
    def test_select_invalid_index_does_not_change_selection(self):
        LIB.ew_parse(b'<select name="s"><option>A</option><option>B</option></select>',b'http://host/')
        self.assertEqual(LIB.ew_select_choose(0,999),-1);self.assertEqual(LIB.ew_select_index(0),0)
        self.assertEqual(LIB.ew_select_choose(999,0),-1);self.assertEqual(LIB.ew_radio_choose(999),-1)
    def test_textarea_initial_entities_and_literal_markup_preserved(self):
        LIB.ew_parse(b'<form method="post"><textarea name="t">first\n&lt;b&gt; &amp; <i>literal</i></textarea><input type="submit"></form>',b'http://host/')
        self.assertEqual(LIB.qa_link_kind(0),11);self.assertEqual(LIB.qa_link_value(0),b'first\n<b> & <i>literal</i>')
        self.assertEqual(self.form_body(1),b't=first%0A%3Cb%3E+%26+%3Ci%3Eliteral%3C%2Fi%3E')
    def test_textarea_unicode_value_preserved(self):
        LIB.ew_parse('<form method="post"><textarea name="t">café</textarea><input type="submit"></form>'.encode(),b'http://host/')
        self.assertEqual(self.form_body(1),b't=caf%C3%A9')

    def test_anchor_id_and_named_target_follow_block_layout(self):
        LIB.ew_parse(b'<p>Before</p><h1 id="heading">Heading</h1><a name="bottom"></a><p>Bottom</p>',b'http://host/')
        self.assertEqual(LIB.ew_anchor_y(b'heading'),LIB.qa_y(1));self.assertEqual(LIB.ew_anchor_y(b'bottom'),LIB.qa_y(2))
    def test_anchor_prefix_does_not_match_and_empty_is_top(self):
        LIB.ew_parse(b'<p id="targetlong">Text</p>',b'http://host/')
        self.assertEqual(LIB.ew_anchor_y(b'target'),-1);self.assertEqual(LIB.ew_anchor_y(b'targetlonger'),-1);self.assertEqual(LIB.ew_anchor_y(b''),0)
    def test_anchor_percent_decodes_but_plus_stays_literal(self):
        LIB.ew_parse(b'<p id="a b">Space</p><p id="a+b">Plus</p>',b'http://host/')
        self.assertEqual(LIB.ew_anchor_y(b'a%20b'),LIB.qa_y(0));self.assertEqual(LIB.ew_anchor_y(b'a+b'),LIB.qa_y(1));self.assertEqual(LIB.ew_anchor_y(b'a%2Bb'),LIB.qa_y(1))
    def test_duplicate_anchor_first_wins(self):
        LIB.ew_parse(b'<p id="same">First</p><p id="same">Second</p>',b'http://host/')
        self.assertEqual(LIB.ew_anchor_y(b'same'),LIB.qa_y(0))
    def test_inline_anchor_does_not_jump_to_document_end(self):
        LIB.ew_parse(b'Before<a name="inline"></a>After<p>Later</p>',b'http://host/')
        self.assertEqual(LIB.ew_anchor_y(b'inline'),LIB.qa_y(0))
    def test_anchor_in_table_uses_final_layout_y(self):
        LIB.ew_parse(b'<table><tr><td>One</td></tr><tr><td id="cell">Two</td></tr></table>',b'http://host/')
        text_index=next(i for i in range(LIB.qa_runs()) if LIB.qa_run_kind(i)==0 and C.string_at(LIB.qa_run_data(i),LIB.qa_run_length(i))==b'Two')
        self.assertEqual(LIB.ew_anchor_y(b'cell'),LIB.qa_y(text_index))

    def document_fetch(self,response):
        server=OneHTTP(response);final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
        try:n=LIB.ew_fetch_document((server.url+'/document').encode(),final,error,128,None)
        finally:server.close()
        return n,C.c_int.in_dll(LIB,'ew_document_type').value,error.value
    def test_document_mime_exact_case_insensitive_and_parameters(self):
        for value,expected in [(b'text/html',0),(b'application/xhtml+xml',0),(b'TeXt/PlAiN; charset=UTF-8',1),(b'image/gif',2),(b'image/png',2),(b'image/jpeg',2),(b'application/octet-stream',3),(b'text/plainx',3)]:
            with self.subTest(value=value):
                n,kind,error=self.document_fetch(b'HTTP/1.0 200 OK\r\ncOnTeNt-TyPe: '+value+b'\r\nContent-Length: 3\r\n\r\nabc')
                self.assertEqual(n,3);self.assertEqual(kind,expected)
    def test_document_missing_type_resets_previous_type_to_html(self):
        self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\na')
        self.assertEqual(self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nb')[:2],(1,0))
    def test_document_redirect_uses_only_final_type(self):
        responses=[b'HTTP/1.0 302 Found\r\nLocation: /final\r\nContent-Type: image/gif\r\nContent-Length: 0\r\n\r\n',b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\na']
        self.assertEqual(self.document_fetch(responses)[:2],(1,1))
    def test_failed_document_fetch_preserves_prior_type(self):
        self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\na')
        n,kind,error=self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: image/gif\r\nContent-Length: 100\r\n\r\nshort')
        self.assertLess(n,0);self.assertEqual(kind,1)
    def test_resource_fetch_does_not_change_document_type(self):
        self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\na')
        self.assertEqual(self.fetch(b'HTTP/1.0 200 OK\r\nContent-Type: image/gif\r\nContent-Length: 3\r\n\r\nGIF')[0],3)
        self.assertEqual(C.c_int.in_dll(LIB,'ew_document_type').value,1)
    def test_local_document_type_by_extension(self):
        for suffix,expected in [('.txt',1),('.TXT',1),('.text',1),('.gif',2),('.PNG',2),('.jpg',2),('.jpeg',2),('.htm',0)]:
            with self.subTest(suffix=suffix),tempfile.NamedTemporaryFile(suffix=suffix) as file:
                file.write(b'data');file.flush();final=C.create_string_buffer(1024);error=C.create_string_buffer(128)
                self.assertEqual(LIB.ew_fetch_document(file.name.encode(),final,error,128,None),4)
                self.assertEqual(C.c_int.in_dll(LIB,'ew_document_type').value,expected)
    def test_select_width_includes_unselected_longest_label(self):
        LIB.ew_parse(b'<select><option selected>A</option><option>A much longer label</option></select>',b'http://host/')
        wide=LIB.qa_run_width_field(0)
        LIB.ew_parse(b'<select><option selected>A</option></select>',b'http://host/')
        self.assertGreater(wide,LIB.qa_run_width_field(0));self.assertLessEqual(wide,240)
    def test_select_actual_width_controls_wrap_and_following_text(self):
        LIB.ew_parse(b'.'*150+b'<select><option>A</option></select>tail',b'http://host/')
        index=next(i for i in range(LIB.qa_runs()) if LIB.qa_run_kind(i)==10)
        self.assertEqual(LIB.qa_y(index),LIB.qa_y(0));self.assertEqual(LIB.qa_x(index+1),LIB.qa_x(index)+LIB.qa_run_width_field(index)+3)
    def test_empty_select_and_unclosed_select_render_bounded_control(self):
        for source in [b'<select></select>',b'<select><option>'+b'W'*100]:
            with self.subTest(source=source):
                LIB.ew_parse(source,b'http://host/')
                index=next(i for i in range(LIB.qa_runs()) if LIB.qa_run_kind(i)==10)
                self.assertGreater(LIB.qa_run_width_field(index),0);self.assertLessEqual(LIB.qa_run_width_field(index),240)

    def test_binary_document_over_html_limit_preserves_every_byte(self):
        body=(bytes(range(256))*782)[:200000]
        n,kind,error=self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        self.assertEqual((n,kind,error),(len(body),3,b''))
        self.assertEqual(bytes(LIB.ew_source_byte(i) for i in range(len(body))),body)
    def test_text_document_remains_bounded_at_html_source_limit(self):
        body=b'x'*120001
        n,kind,error=self.document_fetch(b'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body)
        self.assertEqual(n,119999)
        self.assertEqual(C.c_uint32.in_dll(LIB,'ew_source_length').value,119999)
        self.assertEqual(C.c_int.in_dll(LIB,'ew_fetch_truncated').value,1)

    def test_centered_preformatted_line_with_control_never_shifts_negative(self):
        LIB.ew_parse(b"<center><pre>mpnput type='password' name='p'>'<input>&unknown;text",b'http://host/')
        self.assertTrue(all(LIB.qa_x(i)>=0 for i in range(LIB.qa_runs())))

    def test_latin_named_entities_preserve_case(self):
        LIB.ew_parse(b'&Aacute;&aacute; &Eacute;&eacute; &AElig;&aelig; &OElig;&oelig;',b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b'Aa Ee AEae OEoe')
    def test_latin_literal_numeric_and_named_body_are_consistent(self):
        LIB.ew_parse('Café &#233; &eacute; Straße Æsir Œuvre Þing'.encode(),b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b'Cafe e e Strasse AEsir OEuvre THing')
    def test_combining_accents_do_not_add_question_mark(self):
        LIB.ew_parse('Cafe\u0301 A\u0308 n\u0303'.encode(),b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b'Cafe A n')
    def test_currency_and_symbols_have_explicit_ascii_expansions(self):
        LIB.ew_parse(b'&copy; &reg; &trade; &euro; &pound; &yen; &deg; &plusmn;',b'http://host/')
        self.assertEqual(b''.join(t for t,style,y in self.runs()),b'(c) (R) TM EUR GBP JPY deg +/-')
    def test_latin_form_value_remains_utf8_after_body_transliteration(self):
        LIB.ew_parse(b'<form method="post"><input name="q" value="&Aacute;&aacute;&eacute;"><input type="submit"></form>',b'http://host/')
        self.assertEqual(self.form_body(1),b'q=%C3%81%C3%A1%C3%A9')
    def test_latin_href_remains_utf8_not_ascii_transliteration(self):
        LIB.ew_parse(b'<a href="/caf&eacute;">Caf&eacute;</a>',b'http://host/')
        self.assertEqual(LIB.qa_link(0),'http://host/café'.encode())

    def test_select_option_capacity_is_bounded_and_keeps_following_text(self):
        options=b''.join(b'<option value="'+str(i).encode()+b'">Option '+str(i).encode()+b'</option>' for i in range(65))
        LIB.ew_parse(b'<select name="s">'+options+b'</select><p>AFTER OPTIONS</p>',b'http://host/')
        self.assertEqual(LIB.ew_select_count(0),64);self.assertTrue(LIB.qa_truncated())
        self.assertEqual(LIB.ew_select_choose(0,63),0);self.assertEqual(LIB.ew_select_choose(0,64),-1)
        self.assertIn(b'AFTER OPTIONS',b''.join(t for t,style,y in self.runs()))
    def test_form_field_capacity_is_bounded_and_keeps_following_text(self):
        LIB.ew_parse(b'<input name="q">'*33+b'<p>AFTER FIELDS</p>',b'http://host/')
        self.assertEqual(LIB.qa_links(),32);self.assertTrue(LIB.qa_truncated())
        self.assertIn(b'AFTER FIELDS',b''.join(t for t,style,y in self.runs()))
    def test_select_option_capacity_is_global_and_resets_between_documents(self):
        LIB.ew_parse(b'<select>'+b'<option>x</option>'*40+b'</select><select>'+b'<option>y</option>'*40+b'</select>',b'http://host/')
        self.assertEqual((LIB.ew_select_count(0),LIB.ew_select_count(1)),(40,24))
        LIB.ew_parse(b'<select><option>fresh</option></select>',b'http://host/')
        self.assertEqual(LIB.ew_select_count(0),1);self.assertFalse(LIB.qa_truncated())

if __name__=='__main__':unittest.main(verbosity=2)
