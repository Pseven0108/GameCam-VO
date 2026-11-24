"""CPU-only first-frame diagnosis and postmortem evidence collection; no rerun."""
import base64,io,json,zipfile
from remote_cpu import ROOT,call
code=r'''
import base64,collections,copy,hashlib,io,json,os,pathlib,shutil,stat,subprocess,sys,time,zipfile
os.environ['CUDA_VISIBLE_DEVICES']=''
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1');source=root/'source_candidate';out=root/'attempts/capture'
receipt=json.loads((out/'PROCESS_RECEIPT.json').read_text());assert receipt['exit_code']==1
assert not (root/'C0').exists()
sys.path[:0]=[str(root),str(source)]
import torch,yaml
assert not torch.cuda.is_initialized()
from unittest.mock import patch
diagnostic_out=root/'artifacts/CPU_DATASET_DIAGNOSTIC';diagnostic_out.mkdir(exist_ok=False)
cfg=yaml.safe_load(pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml').read_text())
cfg=copy.deepcopy(cfg);cfg['data']['output']=str(diagnostic_out);(diagnostic_out/cfg['scene']).mkdir(parents=True,exist_ok=True)
manifest=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json')
cfg['data']['input_folder']=str(manifest.parent)
with patch('torch.load',side_effect=RuntimeError('Pretrained weights forbidden in CPU diagnosis')):
 from native_control.dataset import NativeViperRGB
 from src.utils.datasets import RGB_NoPose
 from control_common import ControlError
 stream=NativeViperRGB(cfg,manifest,diagnostic_out)
 ts,color,depth,pose=RGB_NoPose.__getitem__(stream,0)
 checks={'timestamp_matches_index':ts==0,'pose_is_None':pose is None,'depth_is_None':depth is None,
         'shape_is_1_3_360_640':tuple(color.shape)==(1,3,360,640)}
 try:stream[0];strict={'raised':False}
 except ControlError as e:strict={'raised':True,'type':type(e).__name__,'message':str(e)}
 def sha(p):
  h=hashlib.sha256()
  with open(p,'rb') as f:
   for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
  return h.hexdigest()
 diag={'scope':'CPU_ONLY_FIRST_FRAME_NO_MODEL_NO_RETRY','index':0,'RGB_id':1,'timestamp':ts,
       'checks':checks,'failed_predicates':[k for k,v in checks.items() if not v],
       'color':{'shape':list(color.shape),'dtype':str(color.dtype),'device':str(color.device)},
       'depth':{'shape':list(depth.shape),'dtype':str(depth.dtype),'device':str(depth.device),'all_zero':bool((depth==0).all()),
                'nonzero_count':int(torch.count_nonzero(depth)),'sha256':hashlib.sha256(depth.numpy().tobytes()).hexdigest()},
       'pose':None,'source_depth_paths':stream.depth_paths,'source_pose_paths':stream.poses,
       'strict_native_getitem':strict,'native_seen_after_failure':stream.seen,
       'cuda_initialized':torch.cuda.is_initialized(),'checkpoint_deserialized':False,
       'diagnosis':'BaseDataset creates a zero depth placeholder when depth_paths=None; NativeViperRGB requires depth=None and rejects the valid RGB-only upstream return',
       'source_sha256':{'native_control/dataset.py':sha(source/'native_control/dataset.py'),'src/utils/datasets.py':sha(source/'src/utils/datasets.py')}}
assert diag['failed_predicates']==['depth_is_None'] and diag['depth']['all_zero'] and strict['raised']
with (root/'artifacts/FIRST_FRAME_CPU_DIAGNOSIS.json').open('x') as f:json.dump(diag,f,indent=2)
# Preserve every run output; only inspect large backing files at this stage.
files=[]
for p in sorted((out/'shared_cpu').glob('*.bin')):
 s=p.stat();files.append({'path':str(p),'st_dev':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'mode':stat.S_IMODE(s.st_mode),
                         'allocated_bytes':s.st_blocks*512,'sha256':sha(p)})
maps=[];maps_errors=[];own_pgroup=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  text=(proc/'maps').read_text()
  for row in files:
   if row['path'] in text:maps.append({'pid':int(proc.name),'path':row['path']})
  stattext=(proc/'stat').read_text();fields=stattext[stattext.rfind(')')+2:].split()
  if int(fields[2])==json.loads((out/'PROCESS_STARTED.json').read_text())['pgid']:own_pgroup.append(int(proc.name))
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:maps_errors.append(int(proc.name))
gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
trace=[json.loads(line) for line in (out/'native_trace.jsonl').read_text().splitlines() if line.strip()]
kind_counts=dict(collections.Counter(row['kind'] for row in trace))
samples=[json.loads(line) for line in (out/'resource_samples.jsonl').read_text().splitlines() if line.strip()]
peak_gpu=max((int(x['GPU'].split(',')[0]) for x in samples if x.get('GPU_query_exit')==0 and x.get('GPU')),default=None)
rerun=[]
for p in out.rglob('*.rrd'):rerun.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
source_status=subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True)
summary={'status':'BLOCKED_AT_FIRST_RGB_INPUT_CONTRACT','native_lifecycles_started':1,'GPU_process_exit_code':receipt['exit_code'],
 'runtime_seconds':receipt['runtime_seconds'],'tracking_frames_admitted':0,'native_BA_calls':kind_counts.get('native.ba.begin',0),
 'C0_created':False,'complete_C0_bytes':None,'initialization_complete':False,'restore_executed':False,'cross_D_executed':False,
 'formal_B_runs_executed':False,'automatic_retry':False,'CPU_DIAGNOSIS':diag,'trace_kind_counts':kind_counts,
 'sampled_GPU_peak_used_MiB':peak_gpu,'sampled_shm_peak_bytes':receipt['shm_peak_sampled_bytes'],
 'source_commit':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
 'tracked_source_unchanged':source_status=='','source_status':source_status,
 'backing_files':files,'live_backing_maps':maps,'proc_maps_permission_errors':maps_errors,'remaining_own_process_group':own_pgroup,
 'GPU_compute_apps_after':{'exit_code':gpu.returncode,'stdout':gpu.stdout,'stderr':gpu.stderr},
 'rerun_recordings':rerun,'Rerun_browser_verified':False,'Rerun_empty_scene_not_geometry_validation':True,
 'data_disk_after':dict(zip(('total','used','free'),shutil.disk_usage(root))),
 'shm_after':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),
 'historical_files_deleted':0,'temporary_arena_deleted':False,'models_retried':False}
with (root/'artifacts/C0_POSTMORTEM.json').open('x') as f:json.dump(summary,f,indent=2)
selected=[]
for basepath in [root/'artifacts',root/'evidence',root/'operational',out]:
 for p in basepath.rglob('*'):
  if p.is_file() and p.suffix in ('.json','.jsonl','.txt','.py') and p.name!='LAUNCH_INTENT.json' and p.stat().st_size<10*1024**2:
   selected.append(p)
selected.append(root/'RUN_AUTHORIZATION.json')
memory=io.BytesIO()
with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(set(selected)):z.write(p,p.relative_to(root).as_posix())
print(json.dumps({'summary':summary,'artifacts_b64':base64.b64encode(memory.getvalue()).decode()}))
'''
text=call('CPU_DIAGNOSIS_AND_POSTMORTEM',code,timeout=180,
 python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python')
d=json.loads(text.splitlines()[-1]);payload=base64.b64decode(d.pop('artifacts_b64'))
with zipfile.ZipFile(io.BytesIO(payload)) as z:
 assert z.testzip() is None
 target=ROOT/'remote_evidence';target.mkdir(exist_ok=False)
 for name in z.namelist():
  from pathlib import PurePosixPath
  rel=PurePosixPath(name);assert not rel.is_absolute() and '..' not in rel.parts
 z.extractall(target)
(ROOT/'evidence/C0_POSTMORTEM_LOCAL.json').write_text(json.dumps(d['summary'],indent=2))
print(json.dumps({k:v for k,v in d['summary'].items() if k not in ('backing_files','CPU_DIAGNOSIS')}))
print(json.dumps({'CPU_failed_predicates':d['summary']['CPU_DIAGNOSIS']['failed_predicates'],
 'depth_placeholder_all_zero':d['summary']['CPU_DIAGNOSIS']['depth']['all_zero']}))
