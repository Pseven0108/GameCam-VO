from transport import *
code=r'''
import sys,json,pathlib,subprocess,os,hashlib
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);q=r/'control/archive_worker.py';assert not q.exists();q.write_text(p['source']);compile(q.read_text(),str(q),'exec')
with (r/'archives/archive.stdout.txt').open('xb') as so,(r/'archives/archive.stderr.txt').open('xb') as se:
 c=subprocess.Popen(['/usr/bin/python3','-B','-u',str(q),str(r)],cwd=r,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),start_new_session=True)
print(json.dumps({'pid':c.pid,'archive_worker_sha256':hashlib.sha256(q.read_bytes()).hexdigest()}))
'''
print(json.dumps(remote(code,{'root':AUTH['remote_root'],'source':(ROOT/'tools/archive_worker.py').read_text(encoding='utf8')},'RAW_ARCHIVE_LAUNCH',45)))
