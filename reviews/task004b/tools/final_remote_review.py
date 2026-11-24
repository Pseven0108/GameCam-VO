"""Read-only remote terminal audit, permitted only after the sixteen completed runs."""
from transport import *
CODE=r'''import pathlib,sys,json,hashlib,shutil,subprocess,base64
from datetime import datetime,timezone
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);assert (root/'evidence/ALL_SIXTEEN_COMPLETE.json').is_file()
auth=json.loads((root/'release/AUTHORIZATION.json').read_text());lock=json.loads((root/'evidence/LOCKDOWN.json').read_text());verified=[];mismatches=[]
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
for p,h in lock['pins'].items():
 try:actual=sha(p)
 except FileNotFoundError:actual=None
 (verified if actual==h else mismatches).append(dict(path=p,expected=h,actual=actual))
manifest=pathlib.Path(lock['manifest']);rgb=json.loads(manifest.read_text());rgbcheck=[]
for row in rgb['frames']:
 p=(manifest.parent/row['file']).resolve();actual=sha(p);ok=actual==row['sha256'] and p.stat().st_size==row['bytes'];rgbcheck.append(dict(rgb_id=row['rgb_id'],path=str(p),sha256=actual,match=ok))
 if not ok:mismatches.append(dict(path=str(p),reason='RGB_IDENTITY_CHANGED'))
expected=[dict(seed=seed,arm=arm) for seed in (44,45) for arm in auth['orders'][str(seed)]]
terminal=json.loads((root/'evidence/ALL_SIXTEEN_COMPLETE.json').read_text());complete=[];ids=[];serial=True;lastfinish=None
for r in expected:
 d=root/'results'/('seed'+str(r['seed']))/r['arm'];atts=list(d.glob('attempt_*'));assert len(atts)==1;at=atts[0]
 rec=json.loads((at/'PROCESS_RECEIPT.json').read_text());la=json.loads((at/'LAUNCH_RECEIPT.json').read_text());done=json.loads((d/'COMPLETE.json').read_text());ar=json.loads((d/'ARCHIVE_RECEIPT.json').read_text());ctl=json.loads((root/'evidence'/('seed'+str(r['seed'])+'_'+r['arm']+'.control.json')).read_text())
 assert rec['exit_code']==0 and done['poses']==487 and ctl['exit_code']==0
 if lastfinish is not None:serial=serial and la['launched_utc']>=lastfinish
 lastfinish=rec['finished_utc'];ids.append(at.name);complete.append(dict(**r,attempt_id=at.name,process=rec,launch_utc=la['launched_utc'],complete=done,archive=dict(path=ar['path'],sha256=ar['sha256'],bytes=ar['bytes'])))
assert len(set(ids))==16 and serial
ports=[]
for table in ('tcp','tcp6'):
 for line in pathlib.Path('/proc/net',table).read_text().splitlines()[1:]:
  f=line.split();port=int(f[1].split(':')[1],16)
  if f[3]=='0A' and port in (9875,9876,9877):ports.append(dict(port=port,address=f[1].split(':')[0]))
stop=json.loads((root/'evidence/CAMPAIGN_STOP.json').read_text()) if (root/'evidence/CAMPAIGN_STOP.json').is_file() else None
p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
files={}
for q in list((root/'evidence').glob('*.control.*'))+[root/'evidence/ALL_SIXTEEN_COMPLETE.json',root/'evidence/LOCKDOWN.json',root/'evidence/CONTROL_RELEASE_VERIFICATION.json',root/'evidence/CONTROLLER_LAUNCH.json',root/'evidence/controller.stdout.txt',root/'evidence/controller.stderr.txt',root/'control/CONTROL_CONFIG.json']:
 b=q.read_bytes();assert len(b)<2*1024**2;files[q.relative_to(root).as_posix()]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),base64=base64.b64encode(b).decode())
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),verified=verified,mismatches=mismatches,rgb_identity=rgbcheck,campaign_complete=True,order_match=terminal['completed']==expected,serial_no_overlap=serial,run_count=16,attempt_ids_unique=True,runs=complete,stop=stop,rerun_listeners_after=ports,gpu_readonly_query=dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),disk=dict(total=shutil.disk_usage(root).total,free=shutil.disk_usage(root).free),shm=dict(total=shutil.disk_usage('/dev/shm').total,free=shutil.disk_usage('/dev/shm').free),files=files)))
'''
r=rpc(CODE,dict(root=REMOTE),'FINAL_REMOTE_READONLY_PRESERVATION',timeout=360)
files=r.pop('files');r['remote_evidence_files']={n:{k:v for k,v in d.items() if k!='base64'} for n,d in files.items()}
for n,doc in files.items():
 q=ROOT/'remote_evidence'/n;q.parent.mkdir(parents=True,exist_ok=True);data=base64.b64decode(doc['base64']);assert len(data)==doc['bytes'] and hashlib.sha256(data).hexdigest()==doc['sha256'];q.write_bytes(data)
put(ROOT/'evidence/FINAL_REMOTE_PRESERVATION.json',r)
assert not r['mismatches'] and r['order_match'] and r['serial_no_overlap'] and r['stop'] is None and not r['rerun_listeners_after']
print(json.dumps(dict(event='FINAL_REMOTE_PRESERVATION_PASS',pins_verified=len(r['verified']),rgb_verified=len(r['rgb_identity']),new_gpu_runs=r['run_count'],disk_free=r['disk']['free'],service_ports_restored=True)),flush=True)
