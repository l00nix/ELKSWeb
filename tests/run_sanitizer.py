#!/usr/bin/env python3
"""Build sanitizer harness in a temporary directory; preserve command and result."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile, sys
HERE=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path,required=True);a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
sources=[HERE/'fuzz_core.c',HERE.parent/'src/html.c',HERE.parent/'src/url.c',HERE.parent/'src/memory.c',HERE.parent/'font/font.c',HERE.parent/'font/body_font.c']
with tempfile.TemporaryDirectory(prefix='elksweb-asan-') as tmp:
    exe=pathlib.Path(tmp)/'fuzz'
    cmd=['cc','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(HERE.parent/'src'),'-I'+str(HERE.parent/'font'),*[str(p) for p in sources],'-o',str(exe)]
    build=subprocess.run(cmd,capture_output=True,text=True)
    (a.output/'build.log').write_text(build.stdout+build.stderr)
    result={'command':cmd,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'build_returncode':build.returncode}
    if build.returncode==0:
        leaks=sys.platform!='darwin';result['leak_sanitizer']='enabled' if leaks else 'unavailable on macOS; not tested'
        env=dict(os.environ,ASAN_OPTIONS=f'detect_leaks={int(leaks)}:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        run=subprocess.run([str(exe),str((a.output/'failure.htm').resolve())],capture_output=True,text=True,timeout=60,env=env)
        (a.output/'run.log').write_text(run.stdout+run.stderr);result['run_returncode']=run.returncode
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));raise SystemExit(result.get('run_returncode',1))
