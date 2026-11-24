from transport import *
import zipfile
CODE=r'''import sys,pathlib,json
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);auth=json.loads((root/'release/AUTHORIZATION.json').read_text());rows=[]
for seed in (44,45):
 for arm in auth['orders'][str(seed)]:
  d=root/'results'/('seed'+str(seed))/arm;r=dict(seed=seed,arm=arm,status='NOT_STARTED')
  if (d/'COMPLETE.json').exists():r.update(json.loads((d/'COMPLETE.json').read_text()));r['archive']=json.loads((d/'ARCHIVE_RECEIPT.json').read_text())
  elif d.exists():
   r['status']='RUNNING'
   for at in d.glob('attempt_*'):
    if (at/'progress.json').exists():
     try:r['progress']=json.loads((at/'progress.json').read_text())
     except json.JSONDecodeError:pass
  rows.append(r)
print(json.dumps(dict(runs=rows,complete=(root/'evidence/ALL_SIXTEEN_COMPLETE.json').exists(),stop=json.loads((root/'evidence/CAMPAIGN_STOP.json').read_text()) if (root/'evidence/CAMPAIGN_STOP.json').exists() else None)))
'''
finished=[];known=set();last=None;poll=0;started=time.monotonic()
while True:
 poll+=1;d=rpc(CODE,dict(root=REMOTE),'watch_%04d'%poll,timeout=60)
 state=[(r['seed'],r['arm'],r['status']) for r in d['runs']]
 if state!=last:print(json.dumps(dict(event='CAMPAIGN_PROGRESS',runs=state)),flush=True);last=state
 for r in d['runs']:
  key=(r['seed'],r['arm'])
  if r['status']!='COMPLETE' or key in known:continue
  a=r['archive'];label='seed'+str(r['seed'])+'_'+r['arm'];dest=ROOT/'raw_archives'/pathlib.Path(a['path']).name
  assert shutil.disk_usage(ROOT).free>a['bytes']+2*1024**3,'LOCAL_STORAGE_BLOCKED'
  print(json.dumps(dict(event='ARCHIVE_TRANSFER_START',label=label,bytes=a['bytes'])),flush=True)
  err=ROOT/'evidence'/('transfer_'+label+'.ssh.stderr.txt');t0=time.monotonic()
  with dest.open('xb') as out,err.open('xb') as error:
   p=subprocess.run(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,'exec cat -- '+shlex.quote(a['path'])],stdout=out,stderr=error,creationflags=CREATE,timeout=1800)
  assert p.returncode==0 and all(verified(err).values()),'TRANSFER_FAILED'
  assert dest.stat().st_size==a['bytes'] and sha(dest)==a['sha256'],'ARCHIVE_SHA_MISMATCH'
  target=ROOT/'results'/('seed'+str(r['seed']))/r['arm']/a['attempt_id'];target.mkdir(parents=True)
  count=0;skipped=[]
  with zipfile.ZipFile(dest) as z:
   m=json.loads(z.read('_TASK004A_ARCHIVE_MANIFEST.json'));assert m['files']==a['files'] and m['attempt_id']==a['attempt_id']
   assert set(z.namelist())==set(m['files'])|{'_TASK004A_ARCHIVE_MANIFEST.json'}
   for name,e in m['files'].items():
    q=target/name;assert q.resolve().is_relative_to(target.resolve()),'UNSAFE_MEMBER'
    extract=name not in ('native/video.npz','native_rerun.rrd','rerun_recording_print.txt')
    if extract:q.parent.mkdir(parents=True,exist_ok=True)
    h=hashlib.sha256();n=0
    out=q.open('xb') if extract else None
    try:
     with z.open(name) as src:
      while data:=src.read(2**20):h.update(data);n+=len(data);out.write(data) if out is not None else None
    finally:
     if out is not None:out.close()
    assert h.hexdigest()==e['sha256'] and n==e['bytes'],name
    if not extract:skipped.append(name)
    count+=1
  completed={k:v for k,v in r.items() if k!='archive'};put(target.parent/'COMPLETE.json',completed)
  rec=dict(seed=r['seed'],arm=r['arm'],archive=str(dest),bytes=a['bytes'],sha256=a['sha256'],crc='PASS',internal_sha256_matches=count,files=a['files'],archive_only_members=skipped,elapsed_s=time.monotonic()-t0,remote_deleted=False)
  put(ROOT/'evidence'/('LOCAL_ARCHIVE_'+label+'.json'),rec);finished.append(rec);known.add(key)
  print(json.dumps(dict(event='LOCAL_ARCHIVE_VERIFIED',label=label,bytes=a['bytes'],payload_matches=count)),flush=True)
 if d['stop'] is not None:
  put(ROOT/'evidence/CAMPAIGN_REMOTE_STOP.json',d);raise RuntimeError(d['stop'])
 if d['complete']:
  assert len(finished)==16;put(ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json',finished);print('ALL_SIXTEEN_ARCHIVES_VERIFIED',flush=True);break
 assert time.monotonic()-started<4*3600,'SUPERVISION_TIMEOUT_NO_RETRY'
 time.sleep(20)
