"""Admitted GPU-only implementation. Imported only after stdlib preflight passes.

The formal B1/B2/B3/B4 runner remains separately blocked. Each mode below is a
single process lifecycle and cannot continue past RGB080 or call terminate().
"""
import copy,hashlib,json,os,pathlib,time
import cv2
import torch
import torch.multiprocessing as mp
from torch.utils.tensorboard import SummaryWriter
from native_control.runtime import NativeControl,NativeJournal,PrefixComplete,set_active,read_schedule
from native_control.barrier import WriterBarrier
from native_control.binding import capture_c0,restore_c0,rebind_output
from native_control.snapshot import read_manifest
from native_control.dataset import NativeViperRGB
from control_common import ControlError,file_sha,digest
from native_control.stages import mode_spec
from src.slam import SLAM
from src.tracker import Tracker
from src.utils.Printer import Printer
from run import setup_seed


def cached_priors():
    hub=pathlib.Path(os.environ['TORCH_HOME']);torch.hub.set_dir(str(hub));original=torch.hub.load
    official={'yvanyin/metric3d':'yvanyin_metric3d_main','ywyue/FiT3D':'ywyue_FiT3D_main'}
    def local(repo,model,*args,**kwargs):
        if repo not in official or not (hub/official[repo]/'hubconf.py').is_file():raise ControlError('Unadmitted model repository/cache')
        return original(str(hub/official[repo]),model,*args,**{**kwargs,'source':'local'})
    torch.hub.load=local


def native_recording_viewer(video,**kw):
    # Same native geometry/visualizer; file recording avoids public listeners.
    import rerun as rr
    from src.utils import droid_visualization_rerun as vis
    rr.serve_web=lambda **kwargs:None
    vis._to_rr_transform=lambda m:rr.Transform3D(translation=m[:3,3],mat3x3=m[:3,:3])
    original=rr.log
    def log(path,*args,**kwargs):
        if 'timeless' in kwargs:kwargs['static']=kwargs.pop('timeless')
        return original(path,*args,**kwargs)
    rr.log=log
    record_path=pathlib.Path(kw['record_path'])
    vis._gamecam_original_native_viewer(video,**kw)
    if not record_path.is_file() or record_path.stat().st_size==0:raise ControlError('Native Rerun recording missing')


class RestoreIOPrinter:
    """Rebound diagnostic sink; it carries no tracking/optimization state."""
    def __init__(self,context):self.progress_counter=context.Value('i',0)
    def print(self,message,color=None):print(message,flush=True)
    def pbar_ready(self):pass
    def update_pbar(self):self.progress_counter.value+=1
    def terminate(self):pass


class BoundedCaptureSLAM(SLAM):
    """Native parent/spawn construction preserved; only the stop/save control differs."""
    def tracking(self,pipe):
        cached_priors();torch.set_num_threads(2);cv2.setNumThreads(1)
        out=pathlib.Path(os.environ['GAMECAM_NATIVE_ATTEMPT']);lock=json.loads(pathlib.Path(os.environ['GAMECAM_NATIVE_LOCK']).read_text())
        controller=NativeControl(0,out,stage='capture');set_active(controller)
        event_writer=SummaryWriter(self.save_dir);self.tracker=Tracker(self,pipe,event_writer)
        barrier=self.video._native_writer_barrier
        def save(tracker,stream,values,ctrl):
            manifest=capture_c0(out.parent.parent/'C0',tracker,stream,values,ctrl,self.traj_filler,barrier,lock)
            (out/'C0_RECEIPT.json').write_text(json.dumps({'pid':os.getpid(),'state_sha256':manifest['state_sha256'],
                 'actual_boundary_rgb':ctrl.rgb,'next_input_index':values['next_input_index'],
                 'storage_file_bytes':sum(f['bytes'] for f in manifest['files'].values()),'counter':self.video.counter.value},indent=2))
        controller.capture_callback=save
        self.all_trigered+=1
        while self.all_trigered<self.num_running_thread:time.sleep(.001)
        self.printer.pbar_ready()
        try:self.tracker.run(self.stream)
        except PrefixComplete as e:
            if not (out/'C0_RECEIPT.json').is_file():raise ControlError('Initialization did not reach a capturable C0 by RGB080') from e
            (out/'SUCCESS.json').write_text(json.dumps({'mode':'capture','reason':str(e),'pid':os.getpid()}))
        finally:event_writer.flush();event_writer.close();controller.trace.close()
    def terminate(self):raise ControlError('Full termination/Final BA/Filler are not authorized in this bounded smoke')


def capture(root,out,manifest,config,lock):
    import yaml
    cfg=yaml.safe_load(pathlib.Path(config).read_text())
    if file_sha(config)!=lock['r2_yaml_sha256']:raise ControlError('R2 YAML mismatch')
    cfg=copy.deepcopy(cfg);cfg['data'].update(output=str(out),input_folder=str(pathlib.Path(manifest).parent))
    if cfg['tracking']['buffer']!=500 or cfg['stride']!=1 or cfg['setup_seed']!=43:raise ControlError('Frozen R2 settings mismatch')
    setup_seed(43);stream=NativeViperRGB(cfg,manifest,out,stage='capture')
    import numpy as np
    np.testing.assert_array_equal(stream.get_intrinsic().numpy(),[386.01129150390625,386.01129150390625,319.5,179.5])
    os.environ['GAMECAM_NATIVE_CONTROL_BOUNDED']='1'
    slam=BoundedCaptureSLAM(cfg,stream)
    # A separate native visualizer is created by SLAM.run(). No browser is claimed.
    from src.utils import droid_visualization_rerun as vis
    vis.droid_visualization_rerun=native_recording_viewer
    slam.run()
    if slam.visualizer.exitcode!=0:raise ControlError('Native Rerun viewer did not finish successfully')
    if not (out/'SUCCESS.json').is_file():raise ControlError('Capture child failed; no automatic retry')


def restore_and_continue(root,out,mode,lock):
    import task003_observer
    import src.utils.sys_timer as timers
    import sys
    torch.set_num_threads(2);cv2.setNumThreads(1)
    # Resolve frozen prior classes without rerunning either prior model.
    for repo in ('yvanyin_metric3d_main','ywyue_FiT3D_main'):
        path=pathlib.Path(os.environ['TORCH_HOME'])/repo
        if not (path/'hubconf.py').is_file():raise ControlError('Frozen prior source cache missing')
        sys.path.append(str(path))
    torch.cuda.set_device(0)
    torch.empty(0,device='cuda:0')  # Explicit context start inside admitted GPU mode.
    ctx=mp.get_context('spawn');counter=ctx.Value('i',0);barrier=WriterBarrier(ctx)
    printer=RestoreIOPrinter(ctx);event_writer=SummaryWriter(str(out/'native'))
    parent_pipe,pipe=ctx.Pipe()
    observer_file=(out/'observer.jsonl').open('x',encoding='ascii',buffering=1)
    services={'tracker_pipe':pipe,'event_writer':event_writer,'printer':printer,'video_counter':counter,
              'writer_barrier':barrier,'observer_file':observer_file}
    captured=json.loads((root/'attempts/capture/C0_RECEIPT.json').read_text())
    m=read_manifest(root/'C0',captured['state_sha256']);bundle,m,receipt=restore_c0(root/'C0',services=services,expected_sha=captured['state_sha256'],allow_cuda=True)
    if receipt['source_pid']==receipt['new_process_pid']:raise ControlError('Restore did not enter a fresh process')
    (out/'RESTORE_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
    spec=mode_spec(mode)
    expected_source=os.environ['GAMECAM_NATIVE_SOURCE_COMMIT']
    if m['provenance'].get('candidate_source_commit')!=expected_source:
        raise ControlError('C0 was not sealed from this exact final runner source')
    if bundle['cursor']['next_input_index']!=18 or bundle['stream'].seen!=18:
        raise ControlError('Restored C0 cursor does not identify the actual RGB019 input')
    if bundle['control']['rgb']!=18 or not bundle['control']['initialized']:
        raise ControlError('Restored C0 initialization/stage mismatch')
    replay=spec['replay'];schedule=spec['schedule'];D=spec['D'];stage=spec['stage']
    journal=None
    if schedule:
        source_mode=('B1' if schedule=='S1' else 'B4') if spec['formal'] else 'record_'+schedule
        source=root/'attempts'/source_mode/'schedule.jsonl' if replay else None
        header={'c0_sha256':m['state_sha256'],'init_D':0,'W':1,'U':1,'max_rgb':spec['max_rgb'],
                'stage':stage,'schedule':schedule,'producer_D':1 if schedule=='S1' else 0,'consumer_D':D,
                'candidate_source_commit':expected_source,'input_manifest_sha256':lock['input_manifest_sha256']}
        journal=NativeJournal(out/'schedule.jsonl',header,mode='replay' if replay else 'record',source=source)
    controller=NativeControl(D,out,journal=journal,restore_values=bundle['cursor'],stage=stage)
    controller.restore_discrete(bundle['control']);set_active(controller)
    tracker,stream=bundle['tracker'],bundle['stream'];controller.tracker=tracker;controller.video=tracker.video
    stream.set_stage(stage)
    rebind_receipt=rebind_output(bundle,out)
    pathlib.Path(tracker.output).mkdir(parents=True,exist_ok=False)
    bundle['filler'].cfg=tracker.cfg
    bundle['observer'].path=out/'observer.jsonl'
    task003_observer._recorder=bundle['observer']
    timers.timer=bundle['timer']
    for module in list(sys.modules.values()):
        if module is not None and getattr(module,'__name__','').startswith('src.') and getattr(module,'timer',None).__class__ is bundle['timer'].__class__:
            module.timer=bundle['timer']
    (out/'STAGE_RESUME_INPUT.json').write_text(json.dumps({'stage':stage,'next_input':bundle['next_input'],
        'cursor_next_input_index':bundle['cursor']['next_input_index'],'restored_last_rgb':controller.rgb,
        'graph_topology_sha256':digest(controller.context()),'rebind':rebind_receipt},indent=2))
    exit_event=ctx.Event()
    viewer=ctx.Process(target=native_recording_viewer,args=(tracker.video,),kwargs={
        'record_path':str(out/'rerun_stream.rrd'),'exit_event':exit_event,'writer_barrier':barrier})
    viewer.start();printer.pbar_ready()
    succeeded=False
    try:
        if spec['formal']:
            tracker.run(stream)
            if controller.rgb!=487 or stream.seen!=487 or controller.failed:
                raise ControlError('Formal tracker did not consume all 487 ordered RGB inputs')
            # Preserve native final BA and Filler; the shell contributes no optimizer state.
            import numpy as np
            shell=object.__new__(SLAM)
            shell.cfg=tracker.cfg;shell.droid_net=tracker.net;shell.video=tracker.video
            shell.stream=stream;shell.traj_filler=bundle['filler'];shell.printer=printer
            shell.save_dir=tracker.output;shell.device=tracker.device;shell.final_clean=False
            shell.logger=None
            n=int(tracker.video.counter.value)
            np.savez(out/'FRONTEND_KEYFRAMES.npz',timestamps=tracker.video.timestamp[:n].detach().cpu().numpy(),
                poses=tracker.video.poses[:n].detach().cpu().numpy())
            original_backend=shell.backend
            def observed_backend():
                result=original_backend()
                count=int(tracker.video.counter.value)
                np.savez(out/'FINAL_BA_KEYFRAMES.npz',timestamps=tracker.video.timestamp[:count].detach().cpu().numpy(),
                    poses=tracker.video.poses[:count].detach().cpu().numpy())
                return result
            shell.backend=observed_backend
            shell.terminate()
            if not shell.final_clean or stream.filler_seen!=487 or not stream.filler_finished:
                raise ControlError('Native final BA/Filler did not finish all 487 inputs')
            final_file=pathlib.Path(shell.save_dir)/'traj/est_poses_full.txt'
            lines=[x for x in final_file.read_text().splitlines() if x.strip()]
            if len(lines)!=487:raise ControlError('Final exported trajectory does not have 487 rows')
            if not (out/'FINAL_BA_KEYFRAMES.npz').is_file():raise ControlError('Final BA stage output missing')
            journal.seal()
            success={'mode':mode,'stage':stage,'last_rgb':487,'filler_frames':487,'pose_rows':len(lines),
                     'events':journal.index,'ba_calls':controller.ba_calls,'formal_experiment':True,
                     'full_trajectory_file':str(final_file),'full_trajectory_sha256':file_sha(final_file)}
        else:
            try:
                tracker.run(stream)
                raise ControlError('Bounded stage returned without a stage stop')
            except PrefixComplete:
                if controller.rgb!=spec['max_rgb'] or stream.seen!=spec['max_rgb'] or controller.failed:raise
            success={'mode':mode,'stage':stage,'last_rgb':controller.rgb,'next_input_index':stream.seen,
                     'events':journal.index if journal else None,'ba_calls':controller.ba_calls,'formal_experiment':False,
                     'actual_RGB019_consumed':stream.seen>=19,'next_unread_rgb':stream.seen+1}
        success.update(pid=os.getpid(),c0_sha256=m['state_sha256'],candidate_source_commit=expected_source)
        succeeded=True
    finally:
        exit_event.set();barrier.request.clear();viewer.join(timeout=30)
        if viewer.is_alive():
            viewer.terminate();viewer.join(timeout=5)
        printer.terminate();event_writer.flush();event_writer.close();observer_file.close();controller.trace.close()
        if journal and not journal.file.closed:journal.abort()
        if viewer.exitcode!=0:raise ControlError('Native Rerun recording failed during the admitted stage')
    if succeeded:
        (out/'SUCCESS.json').write_text(json.dumps(success,indent=2))
