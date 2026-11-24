"""User-authorized serial continuation; stops on any failure, never retries a model stage."""
import datetime,json,os,pathlib,subprocess,sys,time
from remote import ROOT
py=sys.executable;env=dict(os.environ,CUDA_VISIBLE_DEVICES='')
runid=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
log=ROOT/'evidence'/('R3_RESUME_AFTER_COLLECTION_FIX_'+runid+'.jsonl')
def record(kind,**kw):
 row={'unix':time.time(),'kind':kind,**kw}
 with log.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
def run(script,args):
 q=subprocess.run([py,str(ROOT/'tools'/script),*args],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
 record('tool_receipt',script=script,args=args,exit_code=q.returncode,stdout=q.stdout[-6000:],stderr=q.stderr[-4500:])
 if q.returncode:raise RuntimeError('Continuation stopped after '+script)
 return q
stages=('B1','B2','B4','B3')
record('started',stages=stages,only_serial=True,auto_model_retries=False)
for i,mode in enumerate(stages):
 if i:run('r3_launch_stage.py',[mode])
 poll=1
 while True:
  while (ROOT/'transport'/('R3_POLL_'+mode+'_'+str(poll).zfill(2)+'.receipt.json')).exists():poll+=1
  suffix=str(poll).zfill(2);run('r3_poll_stage.py',[mode,suffix,'--compact'])
  a=json.loads((ROOT/'evidence'/('R3_POLL_'+mode+'_'+suffix+'.json')).read_text())
  if not a['pid_alive']:
   receipt=a['receipts'].get('PROCESS_RECEIPT.json',{});success=a['receipts'].get('SUCCESS.json',{})
   if receipt.get('exit_code')!=0 or not receipt.get('success_receipt_exists') or not success:
    record('stage_failed',mode=mode,receipt=receipt);raise SystemExit(2)
   break
  poll+=1;time.sleep(30)
 run('r3_collect_stage.py',[mode,'02'] if mode=='B1' else [mode])
 run('r3_reclaim_arena.py',[mode])
 record('stage_complete',mode=mode,success=success)
record('all_requested_stages_completed')
