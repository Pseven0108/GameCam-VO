"""Restore the unchanged historical test input, then rerun the full 152 suite."""
import base64,io,json,zipfile
from remote_cpu import ROOT,call
code=r'''
import base64,hashlib,io,json,os,pathlib,subprocess,zipfile
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
raw=subprocess.check_output(['git','-C',str(root/'source_candidate'),'show','0931141cf88247dc8fb0c7628c1d91b6531fea90:src/depth_video.py'])
actual=hashlib.sha256(raw).hexdigest();assert actual=='cb668fab8f2d78c73e0e34efad6c561b9acdbe57df0463b79bd1407e1bfb1f48'
p=root/'source_before/src/depth_video.py';p.parent.mkdir(parents=True,exist_ok=True)
with p.open('xb') as f:f.write(raw)
recovery={'path':str(p),'source_git_commit':'0931141cf88247dc8fb0c7628c1d91b6531fea90','sha256':actual,
 'matches_original_review_preimage':True,'runtime_source_changed':False,'test_assertions_changed':False,'reason':'Missing test fixture in newly isolated workspace'}
(root/'evidence/BASELINE_FIXTURE_RECOVERY.json').write_text(json.dumps(recovery,indent=2))
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='43',
 PYTHONPATH=str(root)+':'+str(root/'source_candidate'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
q=subprocess.run([python,'-B','-u',str(root/'tests/run_release_cpu_tests.py'),'c0_r2_ready'],cwd=root,env=env,capture_output=True,text=True,timeout=240)
result={'name':'ORIGINAL_152_WITH_RESTORED_BASELINE','exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
(root/'artifacts/ORIGINAL_152_READY_PROCESS_RESULT.json').write_text(json.dumps(result,indent=2))
loader=json.loads((root/'artifacts/REAL_LOADER_CPU/CPU_TEST_REPORT.json').read_text())
report=json.loads((root/'artifacts/RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json').read_text())
decision={'CPU_passed':q.returncode==0 and report['total']==report['passed']==152 and loader['total']==loader['passed']==21,
 'real_RGB001_018_checked':loader['first_18_real_frames_checked'],'new_loader_tests_passed':loader['passed'],
 'historical_152_passed':report['passed'],'CUDA_initialized':loader['cuda_initialized'] or report['cuda_initialized'],
 'initial_151_of_152_error_preserved':True,'fixture_recovery':recovery,'GPU_started':False,
 'final_regression_report':'artifacts/RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json'}
assert decision['CUDA_initialized'] is False
(root/'evidence/CPU_PHASE_FINAL_DECISION.json').write_text(json.dumps(decision,indent=2))
memory=io.BytesIO()
with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
 for path in (root/'artifacts/RELEASE_CPU_c0_r2_ready').rglob('*'):
  if path.is_file():z.write(path,path.relative_to(root).as_posix())
 for path in [root/'evidence/CPU_PHASE_FINAL_DECISION.json',root/'evidence/BASELINE_FIXTURE_RECOVERY.json',root/'artifacts/ORIGINAL_152_READY_PROCESS_RESULT.json',p]:z.write(path,path.relative_to(root).as_posix())
print(json.dumps({'decision':decision,'process':result,'artifacts_b64':base64.b64encode(memory.getvalue()).decode()}))
'''
d=json.loads(call('RECOVER_BASELINE_AND_RERUN_152',code,timeout=330,
 python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'))
raw=base64.b64decode(d.pop('artifacts_b64'))
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 dest=ROOT/'CPU_final_evidence';dest.mkdir(exist_ok=False);z.extractall(dest)
(ROOT/'evidence/CPU_PHASE_FINAL_DECISION.json').write_text(json.dumps(d['decision'],indent=2))
print(json.dumps(d))
if not d['decision']['CPU_passed']:raise SystemExit(2)
