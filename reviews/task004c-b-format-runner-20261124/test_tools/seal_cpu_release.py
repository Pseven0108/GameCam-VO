"""Seal the final CPU gate from actual receipts, without GPU execution."""
import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,pathlib,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');s=r/'source_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
assert subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip()=='5d357c1d3079de134dd8b41a20a00632da37f0b0'
assert not subprocess.check_output(['git','-C',str(s),'status','--porcelain','--untracked-files=all'],text=True).strip()
expected={'FORMAT_UNIT_R1':22,'CONFIGDICT_REGRESSION_R1':14,'STAGE_RUNNER_CPU_R1':20,'DRIVER_INTEGRATION_CPU_R2':3,'STAGE_GUARD_CPU_R1':6}
reports={}
for case,count in expected.items():
 p=r/'cpu_tests'/case;process=read(p/'PROCESS_RECEIPT.json');assert process['exit_code']==0
 text=(p/'process.stdout.txt').read_text()
 if case=='CONFIGDICT_REGRESSION_R1':
  last=read(p/'CONFIGDICT_UNIT_TESTS.json');assert last['success'] and last['passed']==count and not last['cuda_initialized']
 else:
  last=json.loads(text.strip().splitlines()[-1]);assert last['failures']==0 and last['errors']==0
 assert last.get('total',last.get('tests'))==count
 reports[case]={'count':count,'process_receipt':process,'result':last}
legacy=read(r/'evidence/CPU_LEGACY152_STAGE_R1_RECEIPT.json');assert legacy['exit_code']==0
legacy_doc=json.loads(legacy['stdout_tail'].strip().splitlines()[-1]);assert legacy_doc['total']==legacy_doc['passed']==152
reports['LEGACY152_FINAL_SOURCE']=legacy_doc
p=r/'cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1';process=read(p/'PROCESS_RECEIPT.json');assert process['exit_code']==0
fresh=read(p/'FRESH_PROCESS_RECEIPT.json');assert fresh['status']=='PASS' and not fresh['CUDA_initialized']
for flag in ('graph_reencode_equal','all_raw_storages_equal','alias_checks_equal','RNG_equal','load_rng_unchanged','forward_and_gradient_all_exact_SHA_equal'):assert fresh[flag]
assert fresh['required_tracker_families']==47 and fresh['unique_storage_files']==849
m=read(p/'corrected_cpu_snapshot/manifest.json')
for key,name in [('src.tracker:Tracker','src/tracker.py'),('native_control.dataset:NativeViperRGB','native_control/dataset.py')]:
 assert m['classes'][key]['source_sha256']==sha(s/name),(key,m['classes'].get(key))
reports['FINAL_SOURCE_REAL_MODEL_ROUNDTRIP']={'receipt':process,'fresh_process':fresh,'source_classes_match_final_candidate':True}
aggregate={'scope':'CPU_FORMAT_AND_STAGE_RUNNER_ACCEPTANCE_NOT_NATIVE_GPU','total':sum(expected.values())+152,'passed':sum(expected.values())+152,'failures':0,'errors':0,'cuda_initialized':False,'real_models_cpu_roundtrip_passed':True,'real_C0_created':False,'RGB019_GPU_verified':False,'Short80_GPU_verified':False,'Formal487_GPU_verified':False,'tests':reports}
(r/'evidence/CPU_FINAL_ACCEPTANCE.json').write_text(json.dumps(aggregate,indent=2))
lock=read(r/'configs/identity_lock.json')
names=subprocess.check_output(['git','-C',str(s),'ls-files'],text=True).splitlines()
pins={'source_candidate/'+n:sha(s/n) for n in names if (s/n).is_file() and not (s/n).is_symlink()}
pins['operational/stage_entry.py']=sha(r/'operational/stage_entry.py')
pins['authorization/TASK_REQUEST.txt']=sha(r/'authorization/TASK_REQUEST.txt')
policy=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/policies/E0.json')
release={'schema':'GAMECAM_TASK004C_STAGE_CPU_RELEASE_V1','candidate_commit':'5d357c1d3079de134dd8b41a20a00632da37f0b0',
'candidate_tree':'c018a65009aaf4f7457e2da5225a5f322a168b77','candidate_pins':pins,'cpu_report_sha256':sha(r/'evidence/CPU_FINAL_ACCEPTANCE.json'),
'input_manifest':'/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json',
'r2_config':'/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml',
'asset_root':'/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data',
'protected_pins':lock['remote_pins'],'runtime_pins':lock['execution_source_pins'],'policy_path':str(policy),'policy_sha256':sha(policy),
'budgets':{'capture':2,'short80':4,'formal487':4},'automatic_retries':0,'native_GPU_validation_pending':True}
with (r/'evidence/CPU_STAGE_RELEASE.json').open('x') as f:json.dump(release,f,indent=2)
print(json.dumps({'cpu_tests':aggregate['total'],'passed':aggregate['passed'],'final_source_real_model_restore':'PASS','candidate_commit':release['candidate_commit'],'candidate_pins':len(pins),'cpu_release_sha256':sha(r/'evidence/CPU_STAGE_RELEASE.json')}))
'''
out=call('FINAL_CPU_STAGE_RELEASE_R2',code,timeout=180)
(ROOT/'evidence/FINAL_CPU_STAGE_RELEASE_R2.json').write_text(out);print(out)
