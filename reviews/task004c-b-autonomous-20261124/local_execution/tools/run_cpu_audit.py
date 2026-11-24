import json,base64,pathlib
from remote_cpu import ROOT,call
raw=(ROOT/'tools/cpu_model_audit.py').read_bytes()
code='''
import pathlib,base64,os,subprocess,json,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
p=r/'operational/cpu_model_audit.py';p.write_bytes(base64.b64decode(B64))
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONHASHSEED='43',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg')
with (r/'evidence/CPU_AUDIT_R0_MODELS.stdout.txt').open('xb') as o,(r/'evidence/CPU_AUDIT_R0_MODELS.stderr.txt').open('xb') as e:
 q=subprocess.run(['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python','-B','-u',str(p)],env=env,cwd=r/'source_candidate',stdout=o,stderr=e,timeout=1200)
receipt={'exit_code':q.returncode,'stdout_bytes':(r/'evidence/CPU_AUDIT_R0_MODELS.stdout.txt').stat().st_size,'stderr_tail':(r/'evidence/CPU_AUDIT_R0_MODELS.stderr.txt').read_text()[-3500:]}
(r/'evidence/CPU_AUDIT_R0_MODELS_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''.replace('B64',repr(base64.b64encode(raw).decode()))
print(call('CPU_MODEL_CLOSURE_AUDIT_R0_MODELS',code,timeout=1250))
