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
        controller=NativeControl(0,out);set_active(controller)
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
    setup_seed(43);stream=NativeViperRGB(cfg,manifest,out)
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
    if mode=='restore_check':
        (out/'SUCCESS.json').write_text(json.dumps({'mode':mode,'hashes_match':True,'pid':os.getpid()}));printer.terminate();event_writer.close();observer_file.close();return
    D=1 if mode in ('record_S1','replay_D1_S0') else 0
    schedule='S1' if mode in ('record_S1','replay_D0_S1') else 'S0'
    replay=mode.startswith('replay_')
    source=root/'attempts'/('record_'+schedule)/'schedule.jsonl' if replay else None
    header={'c0_sha256':m['state_sha256'],'init_D':0,'W':1,'U':1,'max_rgb':80,'schedule':schedule,
            'producer_D':1 if schedule=='S1' else 0,'consumer_D':D}
    journal=NativeJournal(out/'schedule.jsonl',header,mode='replay' if replay else 'record',source=source)
    controller=NativeControl(D,out,journal=journal,restore_values=bundle['cursor']);controller.restore_discrete(bundle['control']);set_active(controller)
    tracker,stream=bundle['tracker'],bundle['stream'];controller.tracker=tracker;controller.video=tracker.video
    rebind_output(bundle,out);bundle['observer'].path=out/'observer.jsonl'
    task003_observer._recorder=bundle['observer']
    timers.timer=bundle['timer']
    # Rebind modules that imported the Timer singleton by value.
    import sys
    for module in list(sys.modules.values()):
        if module is not None and getattr(module,'__name__','').startswith('src.') and getattr(module,'timer',None).__class__ is bundle['timer'].__class__:
            module.timer=bundle['timer']
    exit_event=ctx.Event();viewer=ctx.Process(target=native_recording_viewer,args=(tracker.video,),kwargs={'record_path':str(out/'rerun_stream.rrd'),'exit_event':exit_event,'writer_barrier':barrier})
    viewer.start();printer.pbar_ready()
    try:
        tracker.run(stream)
        raise ControlError('Native bounded tracker returned without a prefix stop')
    except PrefixComplete:
        if controller.rgb!=80 or stream.seen!=80 or controller.failed:raise
        (out/'SUCCESS.json').write_text(json.dumps({'mode':mode,'last_rgb':80,'events':journal.index,'ba_calls':controller.ba_calls,'pid':os.getpid(),'formal_experiment':False},indent=2))
    finally:
        exit_event.set();barrier.request.clear();viewer.join(timeout=15)
        if viewer.is_alive():
            # Only this attempt's own viewer can be stopped; never touch other services.
            viewer.terminate();viewer.join(timeout=5)
        printer.terminate();event_writer.flush();event_writer.close();observer_file.close();controller.trace.close()
        if viewer.exitcode!=0:raise ControlError('Native Rerun recording failed during prefix validation')
