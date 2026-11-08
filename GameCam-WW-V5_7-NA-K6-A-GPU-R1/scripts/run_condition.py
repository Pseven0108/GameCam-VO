"""Independently authorized condition. No model dependencies are imported at module load."""
import argparse,hashlib,importlib,json,os,queue,signal,socket,sys,threading,time,traceback,uuid
from pathlib import Path
from runtime_dependency_pins import RuntimePins,PinError,record_prelaunch_failure
from types import SimpleNamespace
from run_supervisor import LaunchContractError,read_authorization,validate_artifacts,validate_runtime_manifest,claim_condition_attempt,sha
O=Path(__file__).resolve().parents[1]
def log(message):print(time.strftime('%H:%M:%S'),message,flush=True)
class ResultJournal:
 def __init__(self,out):self.out=out;self.sequence=0;(out/'result_events').mkdir(exist_ok=False)
 def save(self,result):
  text=json.dumps(result,indent=2,allow_nan=False);event=self.out/'result_events'/('%06d.json'%self.sequence)
  with event.open('x',encoding='utf-8') as f:f.write(text)
  if self.sequence==0:
   with (self.out/'result.json').open('x',encoding='utf-8') as f:f.write(text)
  else:
   temporary=self.out/('result_'+str(uuid.uuid4())+'.tmp')
   with temporary.open('x',encoding='utf-8') as f:f.write(text)
   temporary.replace(self.out/'result.json')
  self.sequence+=1

def is_torch_oom(exc,torch_module):
 if torch_module is None:return False
 cls=getattr(getattr(torch_module,'cuda',None),'OutOfMemoryError',None)
 return isinstance(exc,cls) if isinstance(cls,type) else False

def main(argv=None,root=O,importer=None):
 parser=argparse.ArgumentParser();parser.add_argument('--method',required=True);parser.add_argument('--case',required=True);parser.add_argument('--monitor-session-id',required=True);parser.add_argument('--attempt-id',required=True);args=parser.parse_args(argv)
 root=Path(root).resolve()
 try:
  # This is a fresh read by the child, independent of the supervisor's own call.
  read_authorization(root,args.method,args.case)
  validate_artifacts(root);validate_runtime_manifest(root)
  pins=RuntimePins(root);static_dependencies=pins.static_check()
  case=next(x for x in json.loads((root/'config/cases.json').read_text(encoding='utf-8-sig')) if x['case_id']==args.case)
  claim_condition_attempt(root,args)
  out=root/'runs'/args.method/args.case
  if out.exists():raise LaunchContractError('CONDITION_OUTPUT_ALREADY_EXISTS','BLOCKED_BY_AUTHORIZATION_GUARD')
  out.mkdir(parents=True,exist_ok=False)
 except (LaunchContractError,PinError,StopIteration,OSError,ValueError) as exc:
  failure=record_prelaunch_failure(root,'condition',exc)
  print(json.dumps(failure),flush=True);return 2
 result=dict(version='K6-A-GPU-R1-01',attempt_id=args.attempt_id,monitor_session_id=args.monitor_session_id,method=args.method,case_id=args.case,status='RUNNING',pid=os.getpid(),started_unix=time.time(),max_frames=120,frames_submitted=0,frames_completed=0,frames=[],initialization=None,native_snapshots=[],mapping_events=[],checkpoint_loads=[],error=None,traceback=None,configuration_matches_K51=False,gt_input=False,trajectory_filler_executed=False,final_BA_executed=False,final_refinement_executed=False)
 result['static_dependencies']=static_dependencies;result['dependency_pin_events']=[]
 journal=ResultJournal(out);save=lambda:journal.save(result);torch_module=None;cv2_module=None;np_module=None;phase='RESULT_INITIALIZATION';exit_code=2
 try:
  save();P=root.parent
  for k,v in dict(PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg',QT_QPA_PLATFORM='offscreen',OMP_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',GAMECAM_XFORMERS_DISABLE_FA3='1',TORCH_HOME=str(P/'data/sota_assets/DROID_W/torch_home'),HF_HOME=str(P/'data/sota_assets/DROID_W/huggingface'),GAMECAM_FIT3D_REPO=str(P/'baselines/droid_w/prior_sources/FiT3D'),GAMECAM_METRIC3D_REPO=str(P/'baselines/droid_w/prior_sources/Metric3D')).items():os.environ[k]=v
  sys.dont_write_bytecode=True
  importer=importer or importlib.import_module
  def pin_event(event):
   result['dependency_pin_events'].append(event)
   if event['event']=='weight_load_started':result['checkpoint_loads'].append(event['requested_path'])
   save()
  pins.event_sink=pin_event
  phase='DEPENDENCY_INSTALL_PIN_GATE';pins.install_before_import()
  phase='DEPENDENCY_IMPORT_TORCH';torch_module=importer('torch');pins.assert_hooks(require_torch=True)
  phase='DEPENDENCY_IMPORT_OPENCV';cv2_module=importer('cv2')
  phase='DEPENDENCY_IMPORT_NUMPY';np_module=importer('numpy')
  phase='NATIVE_RUNTIME'
  exit_code=_native_runtime(root,args,case,out,result,save,torch_module,cv2_module,np_module,pins)
 except BaseException as exc:
  tb=traceback.format_exc()
  if result.get('error'):result.setdefault('secondary_errors',[]).append(dict(error=str(exc),traceback=tb,phase=phase))
  else:result.update(error=str(exc),traceback=tb,error_type=type(exc).__name__)
  if result['status']=='RUNNING':result['status']=exc.code if isinstance(exc,PinError) else ('BLOCKED_BY_GPU_MEMORY' if is_torch_oom(exc,torch_module) else ('BLOCKED_BY_DEPENDENCY_INITIALIZATION' if phase.startswith('DEPENDENCY_') else 'BLOCKED_BY_RUNTIME_TERMINAL'))
  result['failed_phase']=phase;result['torch_import_succeeded']=torch_module is not None;exit_code=2
 finally:
  if result['status']=='RUNNING':result.update(status='BLOCKED_BY_RUNTIME_TERMINAL',error=result['error'] or 'Native runtime returned without a terminal status');exit_code=2
  result['finished_unix']=time.time();result['wall_seconds']=result['finished_unix']-result['started_unix'];result['exit_code']=exit_code;result['terminal']=True
  save()
  print(json.dumps(dict(status=result['status'],exit_code=exit_code,terminal=True,frames_completed=result['frames_completed'],checkpoint_loads=len(result['checkpoint_loads']))),flush=True)
 return exit_code

def _native_runtime(O,args,case,out,r,save,torch,cv2,np,pins):
 """Original native experiment body; only lexical scope and entry/terminal handling change."""
 P=O.parent
 import resource
 pins.assert_hooks(require_torch=True)
 r['runner_sha256']=sha(__file__);r['safety_source_sha256']=sha(O/'scripts/k6a_safety.py');save()
 from k6a_safety import Guard,SafetyStop
 def external_stop(signum,frame):
  p=O/'logs/supervisor_stop.json'
  reason=json.loads(p.read_text()).get('reason') if p.exists() else 'MONITOR_SUPERVISOR_SIGNAL'
  raise SafetyStop(reason)
 signal.signal(signal.SIGTERM,external_stop)
 cv2.setNumThreads(2);torch.set_num_threads(2);torch.manual_seed(43);np.random.seed(43)
 # All loader/network wrappers were installed before importing torch.
 pins.assert_hooks(require_torch=True)
 guard=None;tracker=None;mapper=None;worker=None;worker_error=[];writer=None;handles=[]
 current={'ordinal':None,'started':None,'before_kf':0,'after_filter_kf':0,'force':False}
 last_snapshot=None
 class Printer:
  def print(self,message,*a,**kw):log(str(message))
  def update_pbar(self,*a,**kw):
   nonlocal last_snapshot
   guard.phase='frame_boundary';guard.frame=current['ordinal'];guard.frame_boundary()
   n=int(tracker.video.counter.value);i=current['ordinal']
   r['frames'].append(dict(ordinal=i,published_frame=case['frame_start']+i,native_timestamp=i,accepted_keyframe=n>current['before_kf'],motion_filter_candidate=current['after_filter_kf']>current['before_kf'],keyframes_before=current['before_kf'],keyframes_after=n,force_keyframe=bool(current['force']),frontend_initialized=bool(tracker.frontend.is_initialized),seconds=time.monotonic()-current['started']))
   r['frames_completed']+=1;save();log('FRAME '+str(i+1)+'/120 kf='+str(n)+' initialized='+str(tracker.frontend.is_initialized))
  def __getattr__(self,name):return lambda *a,**k:None
 printer=Printer()
 def snapshot(stage):
  nonlocal last_snapshot
  n=int(tracker.video.counter.value)
  vals=tracker.video.poses[:n].detach()
  disps=tracker.video.disps[:n].detach()
  if not bool(torch.isfinite(vals).all()) or not bool(torch.isfinite(disps).all()):raise FloatingPointError('NONFINITE_NATIVE_STATE')
  stamps=tracker.video.timestamp[:n].detach().cpu().tolist();poses=vals.cpu().tolist()
  initialized=bool(tracker.frontend.is_initialized)
  last_snapshot=dict(stage=stage,at_ordinal=current['ordinal'],initialized=initialized,native_timestamps=stamps,w2c_translation_quaternion_xyzw=poses)
  r['native_snapshots'].append(last_snapshot)
  if initialized and r['initialization'] is None:r['initialization']=dict(ordinal=current['ordinal'],published_frame=case['frame_start']+current['ordinal'],keyframes=n,stage=stage)
  return last_snapshot
 class FrontProxy:
  def __init__(self,base):self.base=base
  def __getattr__(self,k):return getattr(self.base,k)
  def __call__(self,*a,**kw):
   guard.phase='native_frontend';guard.check('frontend_before')
   z=self.base(*a,**kw);guard.check('frontend_after',True);snapshot('frontend_return');save();return z
  def initialize_second_stage(self,*a,**kw):
   guard.phase='initialization_second_stage';guard.check('second_stage_before',True)
   z=self.base.initialize_second_stage(*a,**kw);guard.check('second_stage_after',True);snapshot('second_stage_return');save();return z
 class Stream:
  def __init__(self,base):self.base=base
  def __len__(self):return len(self.base)
  def __getattr__(self,k):return getattr(self.base,k)
  def __getitem__(self,i):
   assert 0<=i<120
   current.update(ordinal=i,started=time.monotonic(),before_kf=int(tracker.video.counter.value));guard.frame=i;guard.phase='input';guard.check('input_before')
   f=case['frames'][i];assert sha(f['path_linux'])==f['png_sha256']
   z=self.base[i];idx,img,depth,pose=z
   assert int(idx)==i and pose is None and list(img.shape)==[1,3,288,512]
   raw=cv2.imread(f['path_linux']);assert hashlib.sha256(raw.tobytes()).hexdigest()==f['decoded_bgr_sha256']
   rgb=(img[0].detach().cpu().permute(1,2,0).numpy()*255).round().astype(np.uint8)
   assert np.array_equal(rgb[:,:,::-1],raw)
   r['frames_submitted']+=1;save();return z
 class Pipe:
  def __init__(self,incoming,outgoing):self.incoming,self.outgoing=incoming,outgoing
  def send(self,x):self.outgoing.put(x)
  def recv(self):
   while True:
    if worker_error:raise worker_error[0]
    if guard.failure:raise SafetyStop(guard.failure)
    try:return self.incoming.get(timeout=.2)
    except queue.Empty:guard.check('pipe_wait')
 class NoMapPipe:
  def send(self,x):
   if not x.get('end'):raise RuntimeError('DROID-W mapping unexpectedly enabled')
  def recv(self):raise RuntimeError('No mapping expected for DROID-W')
 def hook(_module,_input,_output=None):guard.check('module_boundary')
 def wrapped_call(obj,name,phase,after=None):
  base=getattr(obj,name)
  def call(*a,**kw):
   old=guard.phase;guard.phase=phase;guard.check(name+'_before',True);started=time.monotonic()
   z=base(*a,**kw);guard.check(name+'_after',True)
   if after:after(a,kw,z,time.monotonic()-started)
   guard.phase=old;return z
  setattr(obj,name,call)
 try:
  repo=P/'baselines'/('wildgs_slam' if args.method=='wildgs' else 'droid_w')/'upstream'
  os.chdir(repo);sys.path.insert(0,str(repo))
  from src.depth_video import DepthVideo
  from src.modules.droid_net import DroidNet
  from src.tracker import Tracker
  from src.utils.datasets import get_dataset
  cfg_path=P/'GameCam-WW-V5_7-NA-K5_1'/'runs'/args.method/(args.case+'_k5_1')/'effective_config.json'
  cfg=pins.effective_config(out);original=json.loads(json.dumps(pins._checked_original))
  assert cfg['tracking']['buffer']==350 and cfg['tracking']['warmup']==12 and cfg['stride']==1
  verify=json.loads(json.dumps(cfg));verify['max_frames']=original['max_frames'];verify['data']['output']=original['data']['output']
  assert verify==original
  r['configuration_matches_K51']=True;r['reference_config_sha256']=pins.spec['config']['sha256']
  (out/'effective_config.json').write_text(json.dumps(cfg,indent=2))
  r['execution_contract']=dict(repo=str(repo),native_tracker_run=True,capacity=350,precision='unchanged native autocast',mapping_enabled=args.method=='wildgs',schedule='single process with native synchronized tracker/mapper handshake',index_mapping='native timestamps are 0-based stream ordinals; published frame = frame_start + ordinal; K5.1 runner used published labels, uniform offset leaves motion-time differences unchanged',input='K4 RGB+K only; RGB_NoPose has no GT; Mapper est_pose/est_depth come from video')
  guard=Guard(O,out,torch,args.monitor_session_id)
  deadline=time.monotonic()+3
  while guard.latest is None and not guard.failure and time.monotonic()<deadline:time.sleep(.02)
  guard.check('before_model',True)
  stream0=get_dataset(cfg,device='cuda:0');assert len(stream0)==120 and stream0.poses is None and stream0.depth_paths is None
  stream=Stream(stream0)
  net=DroidNet();weights=Path(cfg['tracking']['pretrained']);state=torch.load(str(weights),map_location='cpu',weights_only=True)
  state={k.replace('module.',''):v for k,v in state.items()}
  for k in ['update.weight.2.weight','update.weight.2.bias','update.delta.2.weight','update.delta.2.bias']:state[k]=state[k][:2]
  net.load_state_dict(state,strict=True);del state;net=net.cuda().eval()
  uncer=None
  if args.method=='wildgs':
   guard.phase='mapping_resources'
   from src.mapper import Mapper
   from src.utils.dyn_uncertainty.uncertainty_model import generate_uncertainty_mlp
   uncer=generate_uncertainty_mlp(cfg['mapping']['uncertainty_params']['feature_dim'])
  guard.phase='native_buffer_allocation'
  video=DepthVideo(cfg,printer,uncer_network=uncer) if args.method=='wildgs' else DepthVideo(cfg,printer)
  assert video.poses.shape[0]==350
  slam=SimpleNamespace(cfg=cfg,device='cuda:0',verbose=cfg['verbose'],save_dir=str(out/case['case_id']),printer=printer,droid_net=net,video=video,uncer_network=uncer)
  (Path(slam.save_dir)/'mono_priors/depths').mkdir(parents=True);(Path(slam.save_dir)/'mono_priors/features').mkdir(parents=True)
  q1,q2=queue.Queue(),queue.Queue();trackpipe=Pipe(q2,q1);mappipe=Pipe(q1,q2)
  if args.method=='wildgs':tracker=Tracker(slam,trackpipe)
  else:
   from torch.utils.tensorboard import SummaryWriter
   writer=SummaryWriter(log_dir=str(out/'tensorboard'));tracker=Tracker(slam,NoMapPipe(),writer)
  tracker.frontend=FrontProxy(tracker.frontend)
  old_track=tracker.motion_filter.track
  def observed_motion(*a,**kw):
   guard.phase='motion_filter';guard.check('motion_filter_before')
   z=old_track(*a,**kw);current['after_filter_kf']=int(video.counter.value);current['force']=z;guard.check('motion_filter_after');return z
  tracker.motion_filter.track=observed_motion
  wrapped_call(video,'ba','native_BA')
  r['module_calls']={}
  for name,module in [('DROID',net),('Metric3D',tracker.motion_filter.metric_depth_estimator),('FiT3D',getattr(tracker.motion_filter,'feat_extractor',None)),('MappingUncertainty',uncer)]:
   if module is None:continue
   def count(m,a,z,key=name):r['module_calls'][key]=r['module_calls'].get(key,0)+1
   handles.append(module.register_forward_hook(count))
   for child in module.modules():
    handles.append(child.register_forward_pre_hook(lambda m,i:hook(m,i)))
    handles.append(child.register_forward_hook(hook))
  original_step=torch.optim.Adam.step
  def step(opt,*a,**kw):
   guard.check('Adam.step_before');z=original_step(opt,*a,**kw)
   key='Gaussian' if mapper is not None and opt is mapper.gaussians.optimizer else 'OtherNativeOptimizer'
   r.setdefault('optimizer_steps',{});r['optimizer_steps'][key]=r['optimizer_steps'].get(key,0)+1
   guard.check('Adam.step_after');return z
  torch.optim.Adam.step=step
  if args.method=='wildgs':
   guard.phase='mapper_construction';mapper=Mapper(slam,mappipe,uncer,None,None)
   def mapping_record(name):
    def done(a,kw,z,seconds):
     r['mapping_events'].append(dict(operation=name,frame=current['ordinal'],seconds=seconds,gaussian_count=int(mapper.gaussians.get_xyz.shape[0]),iteration_count=int(getattr(mapper,'iteration_count',0))));save()
    return done
   for name in ['initialize_mapper','initialize_map_opt','map_opt_online','map_opt_online_uncertainty']:
    if hasattr(mapper,name):wrapped_call(mapper,name,'mapping_'+name,mapping_record(name))
   wrapped_call(mapper.gaussians,'extend_from_pcd_seq','gaussian_creation',mapping_record('extend_from_pcd_seq'))
   import src.mapper as mapper_module
   wrapped_call(mapper_module,'render','gaussian_render')
   def mapping_worker():
    try:mapper.run()
    except BaseException as e:
     r['mapper_exception']=dict(error=str(e),traceback=traceback.format_exc());worker_error.append(e);log('MAPPER_STOP '+str(e));save()
   worker=threading.Thread(target=mapping_worker,daemon=True);worker.start()
  pins.assert_hooks(require_torch=True)
  guard.phase='before_tracking';guard.check('models_and_buffers_loaded',True);save()
  log('NATIVE Tracker.run START '+args.method+' '+args.case)
  tracker.run(stream)
  if worker:
   worker.join(timeout=10)
   if worker.is_alive():raise SafetyStop('MAPPER_DID_NOT_EXIT')
   if worker_error:raise worker_error[0]
  guard.phase='bounded_end';guard.check('bounded_end',True);snapshot('bounded_final');r['status']='RUN_COMPLETED'
  assert r['frames_completed']==120
 except BaseException as e:
  r['error']=str(e);r['traceback']=traceback.format_exc()
  if isinstance(e,PinError):r['status']=e.code
  elif isinstance(e,SafetyStop):
   r['status']='BLOCKED_BY_GPU_MEMORY' if any(k in str(e) for k in ['FREE_BELOW','SUSTAINED_MONOTONIC','AVAILABLE_RAM_BELOW','WINDOWS_SHARED_GROWTH','DXGI_BUDGET_DROP','WINDOWS_SHELL_UNRESPONSIVE']) else 'BLOCKED_BY_MONITOR_TRANSPORT'
   r['safety_stop']=str(e)
  elif isinstance(e,torch.cuda.OutOfMemoryError):r['status']='BLOCKED_BY_GPU_MEMORY';r['OOM']=True
  elif guard is not None and ('mapping' in guard.phase or 'gaussian' in guard.phase or worker_error):r['status']='BLOCKED_BY_MAPPING'
  elif isinstance(e,(AssertionError,FileNotFoundError,ImportError)):r['status']='BLOCKED_BY_INPUT_CONTRACT'
  elif tracker is not None and not bool(tracker.frontend.is_initialized):r['status']='BLOCKED_BY_INITIALIZATION'
  else:r['status']='BLOCKED_BY_TRACKING'
  log(r['status']+' '+str(e));traceback.print_exc()
 finally:
  if guard:
   r['resources']=guard.finish();r['stopped_phase']=guard.phase
   r['torch_peak_allocated_MiB']=torch.cuda.max_memory_allocated()/1048576;r['torch_peak_reserved_MiB']=torch.cuda.max_memory_reserved()/1048576
   stats=torch.cuda.memory_stats();r['allocator_OOM_count']=int(stats.get('num_ooms',0));r['allocator_retry_count']=int(stats.get('num_alloc_retries',0))
  if last_snapshot:r['final_native_snapshot']=last_snapshot
  if mapper:
   r['gaussian_count']=int(mapper.gaussians.get_xyz.shape[0]);r['mapping_iterations']=int(getattr(mapper,'iteration_count',0))
  r['finished_unix']=time.time();r['wall_seconds']=r['finished_unix']-r['started_unix'];r['host_peak_RSS_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
  r['output_bytes_before_final_result']=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
  if writer:writer.close()
  save();log('RESULT '+r['status']+' completed='+str(r['frames_completed'])+' submitted='+str(r['frames_submitted']))
 return 0 if r['status']=='RUN_COMPLETED' else 2

if __name__=='__main__':sys.exit(main())
