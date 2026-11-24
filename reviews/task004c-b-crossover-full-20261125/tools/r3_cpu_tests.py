import base64,json
from remote import ROOT,call
payload=base64.b64encode((ROOT/'tests/test_r3_recovery.py').read_bytes()).decode()
code=r'''
import pathlib,base64,json,subprocess,os,time,hashlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
p=r/'tests/test_r3_recovery.py';assert not p.exists();p.write_bytes(base64.b64decode(PAYLOAD))
py='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',GAMECAM_NATIVE_WORKSPACE=str(r),GAMECAM_IO_OVERLAY='0',PYTHONPATH=str(r)+':'+str(r/'overlay')+':'+str(r/'source_candidate'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
receipts=[]
for name in ('test_io_lifecycle','test_r3_recovery','full_buffer_tmpfs_stress'):
 of=r/'evidence'/(name+'.stdout.txt');ef=r/'evidence'/(name+'.stderr.txt');start=time.time()
 with of.open('xb') as out,ef.open('xb') as err:
  q=subprocess.run([py,'-B','-u',str(r/'tests'/(name+'.py'))],env=env,cwd=r,stdout=out,stderr=err,timeout=240)
 a={'test':name,'exit_code':q.returncode,'runtime_seconds':time.time()-start,'stdout_tail':of.read_text()[-1500:],'stderr_tail':ef.read_text()[-4000:],'script_sha256':hashlib.sha256((r/'tests'/(name+'.py')).read_bytes()).hexdigest(),'cuda_visible_devices':env['CUDA_VISIBLE_DEVICES']}
 (r/'evidence'/(name+'.receipt.json')).write_text(json.dumps(a,indent=2));receipts.append(a)
 if q.returncode:break
print(json.dumps({'receipts':receipts,'all_passed':len(receipts)==3 and all(x['exit_code']==0 for x in receipts)}))
'''.replace('PAYLOAD',repr(payload))
a=call('R3_RECOVERY_CPU_TESTS_01',code,timeout=750)
(ROOT/'evidence/R3_RECOVERY_CPU_TESTS_01.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
