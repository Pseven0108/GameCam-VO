from transport import *
code=r'''
import sys,json,pathlib,base64,hashlib
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);files={}
for a in ['E0','E1']:
 d=r/'captures'/a
 for f in ['CAPTURE_COMPLETE.json','STATUS.json','LAUNCH_INTENT.json','model_input.json','native_config.yaml','task004_policy_receipt.json','progress.json','stdout.txt','supervisor.stderr.txt']:
  q=d/f
  if q.is_file():files['captures/'+a+'/'+f]=base64.b64encode(q.read_bytes()).decode()
 for f in ['CHECKPOINT.json','poses.npy','timestamp.npy']:
  q=d/'checkpoint'/f
  if q.is_file():files['native_small/'+a+'/'+f]=base64.b64encode(q.read_bytes()).decode()
for a in ['E0_D1','E0_D0','E1_D1','E1_D0']:
 d=r/'replays'/a
 for f in ['REPLAY_COMPLETE.json','INPUT_RESTORATION.json','STATUS.json','LAUNCH_INTENT.json','stdout.txt','stderr.txt','supervisor.stderr.txt','poses_native.npy','dx_last_inner.npy']:
  q=d/f
  if q.is_file():files['native_small/'+a+'/'+f]=base64.b64encode(q.read_bytes()).decode()
for q in (r/'analysis').glob('*'):
 if q.is_file():files['results/'+q.name]=base64.b64encode(q.read_bytes()).decode()
print(json.dumps({'files':files,'sha256':{k:hashlib.sha256(base64.b64decode(v)).hexdigest() for k,v in files.items()}}))
'''
r=remote(code,{'root':AUTH['remote_root']},'FETCH_SMALL_'+str(time.time_ns()),80)
for f,b64 in r['files'].items():
 b=base64.b64decode(b64);assert hashlib.sha256(b).hexdigest()==r['sha256'][f]
 q=ROOT/f;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
(ROOT/'evidence/SMALL_FILE_IDENTITIES.json').write_text(json.dumps(r['sha256'],indent=2));print(json.dumps({'files':len(r['files']),'bytes':sum(len(base64.b64decode(x)) for x in r['files'].values())}))
