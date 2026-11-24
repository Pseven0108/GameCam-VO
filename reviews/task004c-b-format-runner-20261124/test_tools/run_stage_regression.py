from remote_cpu import call
code=r'''
import pathlib,subprocess,os,json,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(r)+':'+str(r/'source_candidate'),MPLBACKEND='Agg',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
with (r/'evidence/CPU_LEGACY152_STAGE_R1.stdout.txt').open('xb') as o,(r/'evidence/CPU_LEGACY152_STAGE_R1.stderr.txt').open('xb') as e:
 p=subprocess.run(['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python','-B',str(r/'tests/run_release_cpu_tests.py'),'STAGE_R1'],env=env,cwd=r,stdout=o,stderr=e,timeout=900)
receipt={'exit_code':p.returncode,'stdout_tail':(r/'evidence/CPU_LEGACY152_STAGE_R1.stdout.txt').read_text()[-2500:],'stderr_tail':(r/'evidence/CPU_LEGACY152_STAGE_R1.stderr.txt').read_text()[-4000:]}
(r/'evidence/CPU_LEGACY152_STAGE_R1_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
print(call('CPU_LEGACY152_STAGE_R1',code,timeout=950))

