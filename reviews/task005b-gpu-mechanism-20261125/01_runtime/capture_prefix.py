"""TASK005B targeted native prefix capture. No final BA, filler, or full-sequence run."""
import os,sys,pathlib,json,hashlib,time,shutil,traceback,argparse
ROOT=pathlib.Path(__file__).resolve().parents[1]
HIST=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
SRC=HIST/'source_candidate'
sys.path.insert(0,str(SRC));sys.path.insert(0,str(ROOT/'tools'))
C0_SHA='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
TENSOR_NAMES=['poses','disps','intrinsics','selected_prior','targets','weights','uncertainties','temp_y_cdot','dino_feats_resize','affine_weights','eta','ii','jj']
SCALAR_NAMES=['t0','t1','iterations','lm','ep','gamma_data','gamma_prior','gamma_depth','lr','weight_decay','motion_only','depth_only','enable_update_uncer','enable_udba','enable_affine_transform','enable_bidirectional_uncer','debug']
def main():
 a=argparse.ArgumentParser();a.add_argument('--arm',choices=['D1_S1','D0_S1','D1_S0','D0_S0'],required=True);args=a.parse_args();arm=args.arm
 out=ROOT/'attempts'/arm
 if not out.is_dir() or (out/'PROCESS_RECEIPT.json').exists():raise RuntimeError('Fresh admitted attempt required')
 auth=json.loads((ROOT/'AUTHORIZATION.json').read_text());assert auth['approved'] and auth['stop_RGB']==401 and auth['C0_RGB']==18
 assert shutil.disk_usage(ROOT).free>11*1024**3
 import torch,cv2,numpy as np
 import torch.multiprocessing as mp
 from torch.utils.tensorboard import SummaryWriter
 from native_control.native_driver import RestoreIOPrinter,cached_priors
 from native_control.barrier import WriterBarrier
 from native_control.binding import restore_c0,rebind_output
 from native_control.runtime import NativeControl,PrefixComplete,set_active
 from native_control.snapshot import save_prepared_state
 from ba_state_io import prepare_ba_state,ADAPTER_RECEIPT
 from checkpoint.rng_state import capture_rng_state
 from control_common import digest
 from prefix_journal import ReadOnlyPrefixJournal
 import task003_observer
 import src.utils.sys_timer as timers
 import droid_backends
 torch.set_num_threads(2);cv2.setNumThreads(1);cached_priors();torch.cuda.set_device(0)
 for repo in ['yvanyin_metric3d_main','ywyue_FiT3D_main']:sys.path.append(str(pathlib.Path(os.environ['TORCH_HOME'])/repo))
 ctx=mp.get_context('spawn');counter=ctx.Value('i',0);barrier=WriterBarrier(ctx);printer=RestoreIOPrinter(ctx)
 event_writer=SummaryWriter(str(out/'native'));parent_pipe,pipe=ctx.Pipe();observer_file=(out/'observer.jsonl').open('x',buffering=1)
 services={'tracker_pipe':pipe,'event_writer':event_writer,'printer':printer,'video_counter':counter,'writer_barrier':barrier,'observer_file':observer_file}
 bundle,m,receipt=restore_c0(HIST/'C0',services=services,expected_sha=C0_SHA,allow_cuda=True)
 (out/'RESTORE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));assert bundle['cursor']['next_input_index']==18 and bundle['stream'].seen==18
 D=int(arm[1]);S=arm[-2:];schedule=json.loads((ROOT/'evidence/SCHEDULE_PINS.json').read_text())[S]
 journal=ReadOnlyPrefixJournal(schedule['path'],out/'schedule_prefix.jsonl',schedule['sha256'])
 class PrefixControl(NativeControl):
  def frame_begin(self,index,timestamp):
   if int(timestamp)+1>401:raise RuntimeError('TASK005B input bound escaped')
   super().frame_begin(index,timestamp)
  def frame_end(self,tracker,stream,values):
   super().frame_end(tracker,stream,values)
   if self.rgb==401:raise PrefixComplete('TASK005B_RGB401_PREFIX_ONLY')
 ctrl=PrefixControl(D,out,journal=journal,restore_values=bundle['cursor'],stage='formal487');ctrl.restore_discrete(bundle['control']);set_active(ctrl)
 tracker,stream=bundle['tracker'],bundle['stream'];ctrl.tracker=tracker;ctrl.video=tracker.video;stream.set_stage('formal487');rebind_output(bundle,out)
 bundle['filler'].cfg=tracker.cfg;bundle['observer'].path=out/'observer.jsonl';task003_observer._recorder=bundle['observer'];timers.timer=bundle['timer']
 for module in list(sys.modules.values()):
  if module is not None and getattr(module,'__name__','').startswith('src.') and getattr(module,'timer',None).__class__ is bundle['timer'].__class__:module.timer=bundle['timer']
 (out/'FROZEN_CONFIG.json').write_text(json.dumps({'cfg':tracker.cfg,'D':D,'S':S,'source_commit':m['provenance']['candidate_source_commit'],'next_input':bundle['next_input'],'C0_sha256':C0_SHA},default=str,indent=2))
 if tracker.cfg['tracking']['buffer']!=500 or tracker.cfg['stride']!=1 or tracker.cfg['setup_seed']!=43:raise RuntimeError('Frozen R2 changed')
 original=droid_backends.ba;captured=[]
 def capture_ba(*a,**kw):
  phase=task003_observer.recorder().stage
  if ctrl.rgb in (19,233,401) and ctrl.rgb not in captured and phase=='frontend_local_predecision':
   if kw or len(a)!=30:raise RuntimeError('Native BA signature changed')
   scalars=dict(zip(SCALAR_NAMES,a[13:]));assert scalars['iterations']==2 and not scalars['motion_only'] and not scalars['depth_only'] and scalars['enable_udba'] and scalars['enable_update_uncer']
   payload={'tensors':dict(zip(TENSOR_NAMES,a[:13])),'scalars':scalars,'cached_mono':tracker.video.mono_disps,'rng':capture_rng_state(),'slot_rgb_tokens':list(ctrl.nodes)}
   provenance={'artifact_kind':'TASK005B_REAL_BA_INPUT','arm':arm,'D_origin':D,'schedule':S,'rgb':ctrl.rgb,'native_ba_id':ctrl.ba_calls,'observer_stage':phase,'C0_sha256':C0_SHA,'freshly_recaptured':True,'historical_bitwise_recovery_claimed':False,'source_commit':m['provenance']['candidate_source_commit'],'full_input_context_sha256':digest(ctrl.context()),'source_schedule_sha256':schedule['sha256']}
   print(json.dumps({'event':'CAPTURE_BEGIN','arm':arm,'rgb':ctrl.rgb,'native_ba_id':ctrl.ba_calls}),flush=True)
   dest=ROOT/'snapshots'/(arm+'_RGB%03d'%ctrl.rgb)
   prepared=prepare_ba_state(payload,provenance,dest.parent)
   (out/('RGB%03d_STORAGE_BUDGET.json'%ctrl.rgb)).write_text(json.dumps(prepared['budget'],indent=2))
   manifest=save_prepared_state(prepared,dest);captured.append(ctrl.rgb)
   (out/('RGB%03d_CAPTURE_RECEIPT.json'%ctrl.rgb)).write_text(json.dumps({'provenance':provenance,'state_sha256':manifest['state_sha256'],'storage_files':manifest['files'],'budget':prepared['budget']},indent=2))
   print(json.dumps({'event':'CAPTURE_COMPLETE','arm':arm,'rgb':ctrl.rgb,'disk_bytes':sum(x['bytes'] for x in manifest['files'].values()),'disk_free':shutil.disk_usage(ROOT).free}),flush=True)
   del prepared,payload
  return original(*a,**kw)
 droid_backends.ba=capture_ba
 succeeded=False
 try:
  tracker.run(stream)
  raise RuntimeError('Prefix failed to reach explicit boundary')
 except PrefixComplete:
  if ctrl.rgb!=401 or stream.seen!=401 or sorted(captured)!=[19,233,401] or ctrl.failed:raise
  success=journal.finish_prefix();n=int(tracker.video.counter.value)
  np.savez_compressed(out/'PREFIX_KEYFRAMES.npz',timestamps=tracker.video.timestamp[:n].detach().cpu().numpy(),poses=tracker.video.poses[:n].detach().cpu().numpy(),disps=tracker.video.disps[:n].detach().cpu().numpy(),uncertainties=tracker.video.uncertainties[:n].detach().cpu().numpy())
  success.update(arm=arm,D=D,S=S,keyframes=n,captured_RGB=captured,new_input_steps=383,Final_BA=False,Filler=False,peak_cuda_bytes=torch.cuda.max_memory_allocated(),pid=os.getpid())
  (out/'SUCCESS.json').write_text(json.dumps(success,indent=2));print(json.dumps({'event':'PREFIX_COMPLETE',**success}),flush=True);succeeded=True
 finally:
  droid_backends.ba=original;ctrl.trace.close();observer_file.close();event_writer.flush();event_writer.close();printer.terminate()
  if not journal.log.closed:journal.log.close();journal.file.close()
 if not succeeded:raise RuntimeError('Prefix incomplete')
if __name__=='__main__':
 try:main()
 except BaseException:traceback.print_exc();raise
