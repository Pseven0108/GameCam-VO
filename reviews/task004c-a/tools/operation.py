from transport import *
import argparse
p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status']);p.add_argument('mode',choices=['capture','replay']);p.add_argument('key');args=p.parse_args()
code=r'''
import sys,os,json,pathlib,hashlib,subprocess,time,shutil
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);mode=p['mode'];key=p['key']
assert (mode=='capture' and key in ['E0','E1']) or (mode=='replay' and key in ['E0_D1','E0_D0','E1_D1','E1_D0'])
at=r/('captures' if mode=='capture' else 'replays')/key
if p['action']=='start':
 if (r/'STOP.json').exists():raise RuntimeError('campaign stop marker exists')
 if mode=='capture' and key=='E1':assert json.loads((r/'captures/E0/STATUS.json').read_text())['phase']=='complete'
 if mode=='replay':
  assert all(json.loads((r/'captures'/a/'STATUS.json').read_text())['phase']=='complete' for a in ['E0','E1'])
  previous=['E0_D1','E0_D0','E1_D1','E1_D0'];idx=previous.index(key)
  for x in previous[:idx]:assert json.loads((r/'replays'/x/'STATUS.json').read_text())['phase']=='complete'
 for f in list((r/'captures').glob('*/STATUS.json'))+list((r/'replays').glob('*/STATUS.json')):
  assert json.loads(f.read_text())['phase']=='complete',str(f)
 assert not at.exists();at.mkdir()
 receipt=dict(mode='PREFIX_RGB1_328_COMPLETE_NATIVE_CAPTURE' if mode=='capture' else 'ONE_FIXED_NATIVE_BA_REPLAY',arm=key.split('_D')[0],D=int(key[-1]) if mode=='replay' else int(key=='E0'),authorization_sha256=hashlib.sha256((r/'AUTHORIZATION.json').read_bytes()).hexdigest(),created_unix=time.time(),max_attempts=1)
 (at/'LAUNCH_INTENT.json').write_text(json.dumps(receipt,indent=2))
 so=(at/'supervisor.stdout.txt').open('xb');se=(at/'supervisor.stderr.txt').open('xb')
 child=subprocess.Popen(['/usr/bin/python3','-I','-B','-u',str(r/'control/remote_operation.py'),mode,key],cwd=r,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),start_new_session=True)
 print(json.dumps({'launched':True,'supervisor_pid':child.pid,'attempt':str(at),'receipt':receipt}))
else:
 result={'attempt':str(at),'exists':at.exists()}
 for name in ['STATUS.json','progress.json','CAPTURE_COMPLETE.json','REPLAY_COMPLETE.json']:
  if (at/name).is_file():result[name]=json.loads((at/name).read_text())
 for name in ['stderr.txt','supervisor.stderr.txt']:
  if (at/name).is_file():
   with (at/name).open('rb') as f:f.seek(max(0,(at/name).stat().st_size-3500));result[name]=f.read().decode(errors='replace')
 print(json.dumps(result))
'''
r=remote(code,{'root':AUTH['remote_root'],'action':args.action,'mode':args.mode,'key':args.key},args.action.upper()+'_'+args.mode+'_'+args.key+'_'+str(time.time_ns()),50)
if args.action=='status' and r.get('STATUS.json',{}).get('phase')!='failed':
 r={k:v for k,v in r.items() if k not in ['stderr.txt','supervisor.stderr.txt']}
print(json.dumps(r,indent=2))
