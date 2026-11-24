import pathlib,json,sys,subprocess,shlex,base64,time,shutil,os,hashlib,zipfile
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from transport import PRE,ssh_base,HOST,CREATE,verified
REMOTE='/root/rivermind-data/'+ROOT.name
ORDER=['E3','E4','E7','E0','E8','E6','E1','E2']
utc=lambda:datetime.now(timezone.utc).isoformat()
def put(p,d):
 with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def remote(code,payload,name):
 loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<authorized-offline-control>','exec'))"
 command='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
 err=ROOT/'evidence'/f'{name}.ssh.stderr.txt'
 data=base64.b64encode(code.encode())+b'\n'+json.dumps(payload).encode()+b'\n'
 r=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,command],input=data,capture_output=True,creationflags=CREATE,timeout=2400)
 err.write_bytes(r.stderr);(ROOT/'evidence'/f'{name}.stdout.txt').write_bytes(r.stdout)
 assert r.returncode==0 and all(verified(err).values()),(name,r.returncode,r.stderr[-600:])
 return json.loads(r.stdout)
status_code="""
import pathlib,json,sys
s=json.loads(sys.stdin.readline());p=pathlib.Path(s['root']);out={}
for arm in s['order']:
 d=p/'results'/arm
 out[arm]={'attempts':[x.name for x in d.glob('attempt_*')] if d.exists() else [],'complete':(d/'COMPLETE.json').is_file()}
 if out[arm]['complete']:out[arm]['summary']=json.loads((d/'COMPLETE.json').read_text())
print(json.dumps({'arms':out,'resumed_complete':(p/'evidence/ALL_EIGHT_RUNS_COMPLETE.json').is_file(),'resumed_failure':(p/'evidence/DATA_PRIORITY_RESUME_FAILURE.json').is_file()}))
"""
start=time.monotonic();previous=None;n=0
while True:
 n+=1;state=remote(status_code,dict(root=REMOTE,order=ORDER),f'archive_wait_{n:03}')
 compact={a:'COMPLETE' if x['complete'] else 'RUNNING' if x['attempts'] else 'NOT_STARTED' for a,x in state['arms'].items()}
 if compact!=previous:print(json.dumps(dict(event='CAMPAIGN_STATUS',arms=compact)),flush=True);previous=compact
 if state['resumed_failure']:raise RuntimeError('GPU resume failure; archive after review')
 if state['resumed_complete']:
  assert all(x['complete'] and len(x['attempts'])==1 for x in state['arms'].values());break
 assert time.monotonic()-start<4500,'batch wait timeout; no model retry'
 time.sleep(20)
put(ROOT/'evidence/ALL_ARMS_LOCAL_TERMINAL_STATUS.json',state)
( ROOT/'raw_archives').mkdir(exist_ok=True)
( ROOT/'remote_evidence').mkdir(exist_ok=True)
seal_code="""
import pathlib,json,sys,hashlib,os
s=json.loads(sys.stdin.readline());p=pathlib.Path(s['root']);sys.path.insert(0,str(p/'release/tools'))
from archive import seal
from contracts import stat_sha
lock=json.loads((p/'evidence/LOCKDOWN.json').read_text())
bad=[str(q) for q,h in lock['pins'].items() if stat_sha(pathlib.Path(q))!=h]
assert not bad,bad
arc=p/'sealed_results';arc.mkdir(exist_ok=True)
receipts=[]
for arm in s['order']:
 done=json.loads((p/'results'/arm/'COMPLETE.json').read_text());a=pathlib.Path(done['attempt']);z=arc/(arm+'_'+a.name+'.zip');assert not z.exists()
 receipt=seal(a,z,a.name);receipt['arm']=arm;receipts.append(receipt)
 print('',end='',flush=True)
files={}
for q in (p/'evidence').rglob('*'):
 if q.is_file() and q.stat().st_size<2000000:files[str(q.relative_to(p))]=q.read_text(errors='replace')
print(json.dumps({'archives':receipts,'remote_evidence_utf8':files,'protection':{'pinned_files':len(lock['pins']),'mismatches':bad},'disk_free_bytes':__import__('shutil').disk_usage(p).free}))
"""
sealed=remote(seal_code,dict(root=REMOTE,order=ORDER),'seal_all_raw_results')
put(ROOT/'evidence/REMOTE_SEALED_ARCHIVE_RECEIPTS.json',sealed)
for name,text in sealed['remote_evidence_utf8'].items():
 q=ROOT/'remote_evidence'/name;assert q.resolve().is_relative_to((ROOT/'remote_evidence').resolve());q.parent.mkdir(parents=True,exist_ok=True)
 with q.open('x',encoding='utf-8') as f:f.write(text)
receipts=[]
for a in sealed['archives']:
 name=pathlib.PurePosixPath(a['path']).name;dest=ROOT/'raw_archives'/name;needed=a['bytes']*3
 assert shutil.disk_usage(ROOT).free>needed+4*1024**3,'local storage safety reserve'
 print(json.dumps(dict(event='DOWNLOADING_VERIFIED_ARCHIVE',arm=a['arm'],bytes=a['bytes'])),flush=True)
 err=ROOT/'evidence'/('download_'+a['arm']+'.ssh.stderr.txt');t0=time.monotonic()
 with dest.open('xb') as out,err.open('xb') as error:
  r=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,'exec cat -- '+shlex.quote(a['path'])],stdout=out,stderr=error,creationflags=CREATE,timeout=1800)
 assert r.returncode==0 and all(verified(err).values())
 assert dest.stat().st_size==a['bytes'] and sha(dest)==a['sha256'],'archive transfer hash failed'
 target=ROOT/'results'/a['arm']/a['attempt_id'];target.mkdir(parents=True)
 checked=0
 with zipfile.ZipFile(dest) as z:
  m=json.loads(z.read('_TASK004A_ARCHIVE_MANIFEST.json'));assert m['files']==a['files'] and m['attempt_id']==a['attempt_id']
  assert z.testzip() is None
  for n,entry in m['files'].items():
   q=target/n;assert q.resolve().is_relative_to(target.resolve());q.parent.mkdir(parents=True,exist_ok=True)
   h=hashlib.sha256()
   with z.open(n) as src,q.open('xb') as out:
    while chunk:=src.read(2**20):h.update(chunk);out.write(chunk)
   assert h.hexdigest()==entry['sha256'] and q.stat().st_size==entry['bytes'];checked+=1
 put(target.parent/'COMPLETE.json',state['arms'][a['arm']]['summary'])
 rec=dict(arm=a['arm'],archive=str(dest),bytes=a['bytes'],sha256=a['sha256'],crc='PASS',internal_sha256_matches=checked,transfer_elapsed_s=time.monotonic()-t0,remote_deleted=False)
 receipts.append(rec);put(ROOT/'evidence'/('LOCAL_ARCHIVE_'+a['arm']+'.json'),rec)
 print(json.dumps(dict(event='ARCHIVE_VERIFIED',**rec)),flush=True)
put(ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json',receipts)
print('ALL_RAW_RESULTS_TRANSFERRED_AND_VERIFIED',flush=True)