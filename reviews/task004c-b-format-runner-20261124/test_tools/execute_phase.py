"""Execute one already-authorized stage. Never loops or retries a model run."""
import json,sys
from remote_cpu import ROOT,call
mode=sys.argv[1]
assert mode in ('capture','restore_check','record_S1','replay_D0_S1','record_S0','replay_D1_S0','B1','B2','B4','B3')
code=r'''
import hashlib,json,os,pathlib,subprocess,sys,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
mode=json.load(sys.stdin)['mode']
assert mode in ('capture','restore_check','record_S1','replay_D0_S1','record_S0','replay_D1_S0','B1','B2','B4','B3')
log=r/'artifacts'/('STAGE_'+mode)
assert not log.exists(),'This authorized stage was already invoked; no automatic retry'
log.mkdir()
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',GAMECAM_NATIVE_WORKSPACE=str(r))
cmd=[python,'-B','-u',str(r/'runner/run_native_stage.py'),'--mode',mode,'--cpu-report',str(r/'evidence/CPU_FINAL_ACCEPTANCE.json'),'--execute']
start=time.time()
with (log/'stdout.txt').open('xb') as stdout,(log/'stderr.txt').open('xb') as stderr:
 p=subprocess.Popen(cmd,env=env,cwd=r/'source_candidate',stdout=stdout,stderr=stderr)
 (log/'STARTED.json').write_text(json.dumps({'pid':p.pid,'mode':mode,'time':start,'automatic_retry':False}))
 exit_code=p.wait(timeout=2500)
receipt={'mode':mode,'wrapper_exit_code':exit_code,'runtime_seconds':time.time()-start,
 'gpu_run_claimed':(r/'attempts'/mode/'LAUNCH_INTENT.json').is_file(),
 'successful':(r/'attempts'/mode/'SUCCESS.json').is_file(),
 'stdout_tail':(log/'stdout.txt').read_text()[-5000:],'stderr_tail':(log/'stderr.txt').read_text()[-6000:]}
(log/'RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
out=call('AUTHORIZED_GPU_STAGE_'+mode,code,input_bytes=json.dumps({'mode':mode}).encode(),timeout=2550)
(ROOT/'evidence'/('GPU_STAGE_'+mode+'_RECEIPT.json')).write_text(out);print(out)
