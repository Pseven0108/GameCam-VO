import sys,pathlib,json,os,subprocess,hashlib,time,traceback
from datetime import datetime,timezone
root=pathlib.Path(sys.argv[1]);config=json.loads((root/'control/CONTROL_CONFIG.json').read_text());auth=json.loads((root/'release/AUTHORIZATION.json').read_text());done=[];error=None
utc=lambda:datetime.now(timezone.utc).isoformat()
def put(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2)
try:
 for seed in (44,45):
  for arm in auth['orders'][str(seed)]:
   label='seed'+str(seed)+'_'+arm
   with (root/'evidence'/(label+'.control.stdout.txt')).open('xb') as out,(root/'evidence'/(label+'.control.stderr.txt')).open('xb') as err:
    p=subprocess.Popen([sys.executable,'-I','-B','-u',str(root/'control/remote_one.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
    p.stdin.write((json.dumps(dict(root=str(root),seed=seed,arm=arm,viewer_argv=config['viewer_argv']))+chr(10)).encode());p.stdin.close()
    for line in p.stdout:out.write(line);out.flush();sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
    rc=p.wait()
   put(root/'evidence'/(label+'.control.json'),dict(seed=seed,arm=arm,exit_code=rc,utc=utc(),no_retry=True))
   assert rc==0,'RUN_OR_VALIDATION_FAILURE_'+label
   assert (root/'results'/('seed'+str(seed))/arm/'COMPLETE.json').is_file()
   done.append(dict(seed=seed,arm=arm))
 put(root/'evidence/ALL_SIXTEEN_COMPLETE.json',dict(utc=utc(),completed=done,new_gpu_runs=16,automatic_retries=0,shutdown_performed=False))
except BaseException as exc:
 error=repr(exc);put(root/'evidence/CAMPAIGN_STOP.json',dict(utc=utc(),completed=done,error=error,traceback=traceback.format_exc(),no_retry=True));raise
finally:
 print(json.dumps(dict(event='TASK004B_CONTROLLER_FINISHED',completed=done,error=error,shutdown_performed=False)),flush=True)
