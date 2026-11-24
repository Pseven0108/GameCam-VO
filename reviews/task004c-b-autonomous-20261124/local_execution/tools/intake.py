"""Create the resumable run ledger and recover only the authorized source tree."""
import hashlib,json,pathlib,shutil,sys,uuid
from datetime import datetime,timezone,timedelta
ROOT=pathlib.Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1'
shutil.copyfile(PREVIOUS/'tools/remote_cpu.py',ROOT/'tools/remote_cpu.py')
sys.path.insert(0,str(ROOT/'tools'));from remote_cpu import call
state_path=ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json'
assert not state_path.exists(),'Existing task state must be resumed, not recreated'
now=datetime.now(timezone(timedelta(hours=8))).isoformat()
state={'schema':'GAMECAM_AUTONOMOUS_STATE_V1','run_id':'task004c-b-autonomous-'+uuid.uuid4().hex,
 'created_at':now,'status':'RUNNING','phase':'A','source_start_commit':'02f8c8308274489ff7eff83fa9b87b98db74122e',
 'budgets':{'CPU_correction_rounds_used':0,'CPU_correction_rounds_max':2,'new_GPU_C0_lifecycles_used':0,'new_GPU_C0_lifecycles_max':2,
  'historical_GPU_C0_lifecycles_excluded_from_new_budget':2,'restore_lifecycles':0,'short_arms_completed':0,'formal_arms_started':0},
 'phases':{p:{'status':'IN_PROGRESS' if p=='A' else 'NOT_STARTED','source_commit':None,'source_SHA':None,
  'configuration_SHA':None,'input_manifest_SHA':None,'start_time':now if p=='A' else None,'end_time':None,
  'GPU_lifecycle_count':0,'outputs':[],'artifacts_SHA256':{},'stop_reason':None} for p in 'ABCDEFG'},
 'authorization':{'continuous_execution':True,'keep_GPU_allocation_online':True,'restart_instance':False,'shutdown_instance':False,
  'GPU_serial_only':True,'min_data_disk_free_bytes':10*1024**3,'preserve_old_failed_Arenas':True,
  'formal_order':['B1','B2','B4','B3'],'GT_only_offline_phase_G':True,'github_branch':'codex/task004c-b-autonomous-20261124'},
 'next_action':'Read model/runtime owning sources and perform CPU-only closure audit before adapter changes','stop_reason':None}
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md').write_text('# Autonomous execution log\n\n'+now+' — Authorized A→G continuation; no intermediate approval waits. CPU correction budget2; new C0 budget2.\n',encoding='utf-8')
request=pathlib.Path(r'C:\Users\Administrator\.codex\attachments\bf9596be-42d5-4637-a29a-c663aaf3d09c\已粘贴的文本.txt')
(ROOT/'authorization').mkdir(exist_ok=True)
(ROOT/'authorization/USER_AUTHORIZATION.txt').write_bytes(request.read_bytes())
code=r'''
import hashlib,json,pathlib,subprocess,shutil,sys
origin=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
assert subprocess.check_output(['git','-C',str(origin/'source_candidate'),'rev-parse','HEAD'],text=True).strip()=='02f8c8308274489ff7eff83fa9b87b98db74122e'
assert not subprocess.check_output(['git','-C',str(origin/'source_candidate'),'status','--porcelain','--untracked-files=no'])
root.mkdir(exist_ok=False)
for name in ['evidence','artifacts','operational','attempts','cpu_tests','source_before','publication']:(root/name).mkdir()
q=subprocess.run(['git','clone','--no-hardlinks','--local',str(origin/'source_candidate'),str(root/'source_candidate')],capture_output=True,text=True,timeout=60);assert q.returncode==0
src=root/'source_candidate'
subprocess.run(['git','-C',str(src),'switch','-c','codex/task004c-b-autonomous-20261124'],check=True,capture_output=True)
for key,fmt in [('user.name','%an'),('user.email','%ae')]:
 value=subprocess.check_output(['git','-C',str(src),'log','-1','--format='+fmt],text=True).strip()
 subprocess.run(['git','-C',str(src),'config',key,value],check=True)
for name in ['native_control','checkpoint','schedule','runner','control_common.py']:(root/name).symlink_to(src/name,target_is_directory=(src/name).is_dir())
shutil.copytree(src/'tests',root/'tests');shutil.copytree(origin/'configs',root/'configs')
shutil.copyfile(origin/'evidence/FILE_BACKED_CPU_VALIDATION.json',root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
dest=root/'source_before/src';dest.mkdir(parents=True)
raw=subprocess.check_output(['git','-C',str(src),'show','0931141cf88247dc8fb0c7628c1d91b6531fea90:src/depth_video.py']);(dest/'depth_video.py').write_bytes(raw)
shutil.copyfile(origin/'evidence/APPROVED_47_FAMILY_PROTOCOL.json',root/'evidence/APPROVED_47_FAMILY_PROTOCOL.json')
state=json.load(sys.stdin);(root/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(state,indent=2))
for path in (origin/'attempts/capture/shared_cpu').glob('*.bin'):
 assert path.is_file() and path.stat().st_size in (1382400000,864000000)
hub=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub')
requested={
 'img_feature_extractors.py':src/'src/utils/mono_priors/img_feature_extractors.py',
 'metric_hubconf.py':hub/'yvanyin_metric3d_main/hubconf.py',
 'metric_monodepth.py':hub/'yvanyin_metric3d_main/mono/model/monodepth_model.py',
 'fit3d_hubconf.py':hub/'ywyue_FiT3D_main/hubconf.py',
 'slam_termination.py':src/'src/slam.py',
 'runtime.py':src/'native_control/runtime.py',
 'snapshot.py':src/'native_control/snapshot.py',
 'rng_state.py':src/'checkpoint/rng_state.py',
 'native_driver.py':src/'native_control/native_driver.py'}
texts={}
for name,path in requested.items():
 raw=path.read_bytes();texts[name]={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'text':raw.decode()}
result={'source_commit':'02f8c8308274489ff7eff83fa9b87b98db74122e','disk':dict(zip(('total','used','free'),shutil.disk_usage(root))),
 'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'sources':texts,'GPU_launched':False,
 'CPU_real_weight_forward_authorized':True,'historical_Arena_preserved':True}
(root/'evidence/INTAKE.json').write_text(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2))
print(json.dumps(result))
'''
d=json.loads(call('AUTONOMOUS_INTAKE',code,input_bytes=json.dumps(state).encode(),timeout=120))
sources=d.pop('sources');dest=ROOT/'source_intake';dest.mkdir(exist_ok=True)
for name,value in sources.items():
 raw=value.pop('text').encode();assert hashlib.sha256(raw).hexdigest()==value['sha256'];(dest/name).write_bytes(raw)
(ROOT/'evidence/SOURCE_INTAKE_MANIFEST.json').write_text(json.dumps(sources,indent=2))
(ROOT/'evidence/INTAKE.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
