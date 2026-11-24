import json,sys
from transport import ROOT,rpc
arm=sys.argv[1];nonce=sys.argv[2]
root=json.loads((ROOT/'release/AUTHORIZATION.json').read_text())['remote_root']
code="""import json,pathlib,subprocess
root=pathlib.Path(ROOT+'/results/'+ARM)
for a in root.glob('attempt_*'):
 print('ATTEMPT',a.name)
 for name in ['progress.json','PROCESS_RECEIPT.json','VALIDATION_FAILED.json','native_camera_stream.json']:
  p=a/name
  if p.exists(): print(name,p.read_text())
 for name in ['process.stdout.txt','process.stderr.txt']:
  p=a/name
  if p.exists():
   with p.open('rb') as f:f.seek(max(0,p.stat().st_size-1000));print(name,f.read().decode(errors='replace'))
print(subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout)
""".replace('ROOT',repr(root)).replace('ARM',repr(arm))
rpc(code,'STATUS_'+arm+'_'+nonce,30)
