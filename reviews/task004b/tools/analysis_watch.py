"""Supervise CPU post-processing only. Cannot start GPU work."""
import os,sys,json,pathlib,time,subprocess
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1];ev=ROOT/'evidence';started=time.monotonic();last=-1
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
def call(script,label):
 args=[sys.executable,'-X','utf8',str(ROOT/'tools'/script)];t=time.monotonic()
 with (ev/(label+'.stdout.txt')).open('xb') as out,(ev/(label+'.stderr.txt')).open('xb') as err:
  p=subprocess.run(args,stdout=out,stderr=err,timeout=1200,cwd=ROOT)
 with (ev/(label+'.process.json')).open('x') as f:json.dump(dict(argv=args,exit_code=p.returncode,elapsed_s=time.monotonic()-t,utc=datetime.now(timezone.utc).isoformat(),gpu_execution=False),f,indent=2)
 assert p.returncode==0,(ev/(label+'.stderr.txt')).read_text(errors='replace')[-3000:]
 print(json.dumps(dict(event='CPU_POSTPROCESS_COMPLETE',label=label)),flush=True)
while True:
 if (ev/'CAMPAIGN_REMOTE_STOP.json').exists():raise RuntimeError('GPU campaign stopped; no automatic model replay')
 n=len(list(ev.glob('LOCAL_ARCHIVE_seed*.json')))
 if n!=last:
  call('analyze_repeated.py','cpu_available_'+str(n).zfill(2));last=n
 if (ev/'ALL_LOCAL_ARCHIVES_VERIFIED.json').exists():
  assert n==16;call('summarize_repeated.py','cpu_statistics_all24');print('ALL24_POSTPROCESSING_FINISHED',flush=True);break
 assert time.monotonic()-started<4*3600,'CPU_POSTPROCESS_WATCH_TIMEOUT'
 time.sleep(20)
