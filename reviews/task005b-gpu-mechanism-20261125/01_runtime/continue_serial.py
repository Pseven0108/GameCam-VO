"""Serial bounded continuation; no numerical retries. Archives only this task's outputs."""
import pathlib,sys,subprocess,json,time,hashlib,traceback,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];RT=ROOT/'01_runtime';sys.path.insert(0,str(RT));from ssh_execute import ssh,base
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
REMOTE='/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1';ARMS=['D1_S1','D0_S1','D1_S0','D0_S0'];RGB=[19,233,401]
EVENT=ROOT/'04_results/SUPERVISOR_EVENTS.jsonl';EVENT.parent.mkdir(exist_ok=True)
def log(event,**data):
 row={'unix':time.time(),'event':event,**data}
 with EVENT.open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
def remote(code,label):
 n=len(list((ROOT/'00_intake').glob('AUTO_*_RECEIPT.json')))+1;tag='AUTO_%03d_'%n+label
 of=ROOT/'00_intake'/(tag+'.stdout.txt');ef=ROOT/'00_intake'/(tag+'.stderr.txt');start=time.time()
 with of.open('xb') as out,ef.open('xb') as err:
  q=subprocess.run(base()+['-o','ClearAllForwardings=yes',ssh.HOST,'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -'],input=code.encode(),stdout=out,stderr=err,timeout=180,creationflags=ssh.CREATE)
 receipt={'exit_code':q.returncode,'trust':ssh.verified(ef),'seconds':time.time()-start,'label':label}
 (ROOT/'00_intake'/(tag+'_RECEIPT.json')).write_text(json.dumps(receipt,indent=2))
 if q.returncode or not all(receipt['trust'].values()):raise RuntimeError('Remote command failed '+str(of))
 return json.loads(of.read_text())
def status(arm,state=None):
 code="""import pathlib,json,shutil,subprocess
r=pathlib.Path(REMOTE)
arm=ARM;state=STATE
p=(r/'attempts'/arm) if state is None else (r/'evidence'/('REPLAY_CONTEXT02_'+state))
x={'exists':p.exists(),'disk_free':shutil.disk_usage(r).free,'gpu_pids':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()}
for n in ['LAUNCH_RECEIPT.json','PROCESS_RECEIPT.json','SUCCESS.json']:
 if (p/n).exists():x[n]=json.loads((p/n).read_text())
if state:
 d=r/'results_context02'/state
 for n in ['SUCCESS.json','ENDPOINT_FAILURE.json']:
  if (d/n).exists():x[n]=json.loads((d/n).read_text())
f=p/'stdout.txt'
if f.exists():
 with f.open('rb') as s:s.seek(max(0,f.stat().st_size-500));x['tail']=s.read().decode(errors='replace')
print(json.dumps(x))
""".replace('REMOTE',repr(REMOTE)).replace('ARM',repr(arm)).replace('STATE',repr(state))
 return remote(code,'STATUS_'+(state or arm))
def wait_finish(arm,state=None):
 last=''
 while True:
  s=status(arm,state)
  if s['disk_free']<10*1024**3:raise RuntimeError('STORAGE_BELOW_10_GIB; no next run permitted')
  if 'ENDPOINT_FAILURE.json' in s:raise RuntimeError('Native endpoint mismatch; STOP without numerical retry')
  p=s.get('PROCESS_RECEIPT.json')
  if p:
   if p['exit_code']!=0 or not p['success_exists'] or 'SUCCESS.json' not in s:raise RuntimeError('Failed process: '+json.dumps(s))
   if state:
    assert s['SUCCESS.json']['PASS'] and s['SUCCESS.json']['total_native_calls']==12
    assert all(x['PASS'] for x in s['SUCCESS.json']['endpoint_checks'])
   log('PROCESS_COMPLETE',arm=arm,state=state,receipt=p);return s
  tail=s.get('tail','')
  if tail and tail!=last:log('RUN_PROGRESS',arm=arm,state=state,tail=tail);last=tail
  time.sleep(20)
def launch(arm,state=None):
 if state:
  text=(RT/'launch_context02_template.py.txt').read_text().replace('name=STATE','name='+repr(state))
 else:text=(RT/'launch_capture_template.py.txt').read_text().replace('arm=ARM','arm='+repr(arm))
 # Convert exclusive launch receipt output into one JSON document.
 result=remote(text,'LAUNCH_'+(state or arm));log('LAUNCHED',arm=arm,state=state,receipt=result)
def collect(state,kind):
 proof=RECEIVER/(kind+'_'+state+'.VERIFIED.json');artifact=RECEIVER/(kind+'_'+state+'.tar')
 if proof.exists():
  x=json.loads(proof.read_text());h=hashlib.file_digest(artifact.open('rb'),'sha256').hexdigest();assert h==x['archive_sha256'] and artifact.stat().st_size==x['archive_bytes'];log('ARCHIVE_ALREADY_VERIFIED',state=state,kind=kind);return x
 assert not artifact.exists(),'Partial local transfer needs explicit reconciliation'
 assert shutil.disk_usage(RECEIVER).free>5*1024**3
 q=subprocess.run([sys.executable,str(RT/'collect_context02_artifact.py'),state,kind],cwd=ROOT,capture_output=True,text=True,timeout=900)
 (ROOT/'04_results'/('TRANSFER_'+kind+'_'+state+'.txt')).write_text(q.stdout+q.stderr)
 if q.returncode:raise RuntimeError('Archive transfer/verification failure: '+q.stdout+q.stderr)
 x=json.loads(proof.read_text());log('ARCHIVED',state=state,kind=kind,bytes=x['archive_bytes'],sha256=x['archive_sha256']);return x
def retire(arm,proofs):
 # Only byte-identical, task-owned snapshot and result copies are eligible.
 code="""import pathlib,json,hashlib,os,subprocess,shutil,time
r=pathlib.Path(REMOTE).resolve();arm=ARM;proofs=PROOFS
assert r.name=='GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
assert json.loads((r/'attempts'/arm/'PROCESS_RECEIPT.json').read_text())['exit_code']==0
items=[]
for proof in proofs:
 state=proof['state'];assert state.startswith(arm+'_RGB') and proof['source_removed'] is False
 rel=('snapshots' if proof['kind']=='snapshot' else 'results_context02')+'/'+state
 d=r/rel;assert d.is_dir() and not d.is_symlink() and d.resolve().is_relative_to(r)
 if proof['kind']=='result':assert json.loads((r/'evidence'/('REPLAY_CONTEXT02_'+state)/'PROCESS_RECEIPT.json').read_text())['exit_code']==0
 files={p.relative_to(d).as_posix():p for p in d.rglob('*') if p.is_file()};assert set(files)==set(proof['members'])
 identities=[]
 for n,p in files.items():
  assert not p.is_symlink() and p.resolve().is_relative_to(d.resolve())
  v=proof['members'][n];before=p.stat();assert before.st_size==v['bytes']
  digest=hashlib.sha256()
  with p.open('rb') as f:
   for block in iter(lambda:f.read(8*1024**2),b''):digest.update(block)
  got=digest.hexdigest()
  assert got==v['sha256'];after=p.stat();assert (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
  identities.append({'relative':n,'ino':after.st_ino,'bytes':after.st_size,'mtime_ns':after.st_mtime_ns,'sha256':got})
 items.append((d,proof,identities))
roots=[str(d)+'/' for d,_,_ in items];active=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  for f in (proc/'fd').iterdir():
   try:t=os.readlink(f)
   except FileNotFoundError:continue
   if any(t.startswith(q) for q in roots):active.append([proc.name,t])
  maps=(proc/'maps').read_text()
  for q in roots:
   if q in maps:active.append([proc.name,'mapped '+q])
 except (FileNotFoundError,ProcessLookupError):pass
assert not active,active
logdir=r/'retirement';logdir.mkdir(exist_ok=True);dest=logdir/(arm+'.json');assert not dest.exists()
receipt={'arm':arm,'only_current_task_owned':True,'historical_files_deleted':False,'active_descriptors_or_maps':active,'copied_to_local_and_SHA_verified':True,'items':[{'source':str(d),'local_archive':proof['archive'],'archive_sha256':proof['archive_sha256'],'files':identities} for d,proof,identities in items],'unix':time.time(),'completed':False}
dest.write_text(json.dumps(receipt,indent=2))
for d,proof,identities in items:
 for p in d.rglob('*'):assert not p.is_symlink()
 shutil.rmtree(d)
receipt['completed']=True;receipt['disk_free_after']=shutil.disk_usage(r).free;dest.write_text(json.dumps(receipt,indent=2))
print(json.dumps({'arm':arm,'completed':True,'disk_free_after':receipt['disk_free_after'],'archived_directories':len(items)}))
""".replace('REMOTE',repr(REMOTE)).replace('ARM',repr(arm)).replace('PROOFS',repr(proofs))
 x=remote(code,'RETIRE_'+arm);log('CURRENT_TASK_REMOTE_COPIES_RETIRED',**x)
def main():
 log('SUPERVISOR_START',arms=ARMS,stop_RGB=401,max_native_calls=144,automatic_numerical_retries=False,original_setup_failure_native_calls=0)
 for arm in ARMS:
  p=status(arm)
  if not p['exists']:launch(arm)
  wait_finish(arm)
  proofs=[]
  for rgb in RGB:
   state=arm+'_RGB%03d'%rgb;proofs.append(collect(state,'snapshot'))
   p=status(arm,state)
   if not p['exists']:launch(arm,state)
   wait_finish(arm,state);proofs.append(collect(state,'result'))
  retire(arm,proofs)
 log('ALL_AUTHORIZED_GPU_WORK_COMPLETE',prefixes=4,states=12,mechanism_native_calls=144,new_frame_steps=1532,final_BA=False,filler=False)
 (ROOT/'04_results/SUPERVISOR_SUCCESS.json').write_text(json.dumps({'PASS':True,'prefixes':4,'contexts':12,'native_calls':144,'automatic_retries':0,'setup_attempts':2,'shutdown_performed':False},indent=2))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  log('STOPPED',error=str(e));(ROOT/'04_results/SUPERVISOR_STOP.json').write_text(json.dumps({'error':str(e),'traceback':traceback.format_exc(),'no_next_run_started':True},indent=2));raise
