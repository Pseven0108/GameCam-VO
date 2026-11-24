import json
from remote_cpu import ROOT,call
raw=(ROOT/'tools/cpu_closure_roundtrip.py').read_bytes()
code=r'''
import pathlib,sys,os,subprocess,json
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1');p=r/'operational/cpu_closure_roundtrip.py';p.write_bytes(sys.stdin.buffer.read())
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONHASHSEED='43',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MPLBACKEND='Agg')
with (r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION.stdout.txt').open('xb') as o,(r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION.stderr.txt').open('xb') as e:
 q=subprocess.run(['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python','-B','-u',str(p)],env=env,cwd=r/'source_candidate',stdout=o,stderr=e,timeout=1800)
receipt={'exit_code':q.returncode,'stdout_tail':(r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION.stdout.txt').read_text()[-2500:],'stderr_tail':(r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION.stderr.txt').read_text()[-4500:]}
(r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
print(call('CPU_REAL_MODEL_ROUNDTRIP_R2_RNG_VALIDATION',code,input_bytes=raw,timeout=1850))
