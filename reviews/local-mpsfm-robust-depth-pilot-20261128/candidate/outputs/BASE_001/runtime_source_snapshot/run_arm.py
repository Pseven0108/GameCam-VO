"""MP-SfM-style robust depth-prior local exploratory run using the frozen native Tracker/BA/filler.

Differences from remote formal protocol: local Torch/cu128, buffer96 with no
capacity event, single-process native Tracker, prerecomputed common priors,
PyTorch SDPA Metric3D backend, no online viewer. These apply to every arm.
"""
import argparse, importlib.util,json,time,traceback,types,shutil
import numpy as np
from runtime_local import *
import torch

class Printer:
    def print(self,message,*args,**kwargs):print(str(message),flush=True)
    def update_pbar(self,*args,**kwargs):pass
    def pbar_ready(self,*args,**kwargs):pass

class Pipe:
    def send(self,value):pass

def load_extension():
    p=ROOT/'toolchain/build/robust_sm120_001/local_mpsfm_robust_c3414af6.so'
    spec=importlib.util.spec_from_file_location('local_mpsfm_robust_c3414af6',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['BASE','A5','ROBUST','ROBUST_A5'],required=True)
    ap.add_argument('--attempt',default='001');a=ap.parse_args()
    out=TASK/'outputs'/f'{a.arm}_{a.attempt}'
    out.mkdir(exist_ok=False)
    write(out/'ATTEMPT.json',dict(status='STARTED',arm=a.arm,seed=43,frames=64,
        buffer=96,window=manifest()['window'],scope='LOCAL_EXPLORATORY_NOT_REMOTE_FORMAL',remote_connections=0,
        source_gate_version=1,algorithm_change='Cauchy IRLS prior; independent eta damping; reweight within both native iterations'))
    snapshot=out/'runtime_source_snapshot';snapshot.mkdir()
    for src in [TASK/'scripts/run_arm.py',TASK/'scripts/runtime_local.py',TASK/'src/robust_controller.py',TASK/'src/robust_math.py',TASK/'src/gpu_verification.py',TASK/'src/endpoint_check.py']:
        shutil.copyfile(src,snapshot/src.name)
    torch.set_num_threads(4)
    from src.utils.common import setup_seed
    from src.modules.droid_net import DroidNet
    from src.depth_video import DepthVideo
    from src.tracker import Tracker
    from src.frontend import Frontend
    from src.backend import Backend
    from src.trajectory_filler import PoseTrajectoryFiller
    from torch.utils.tensorboard import SummaryWriter
    from collections import OrderedDict
    from controller import coefficient_map,arm_config
    from robust_controller import install,MAIN
    from gpu_verification import check as endpoint_check
    cfg=config(out);setup_seed(43)
    import yaml
    (out/'native_config.yaml').write_text(yaml.safe_dump(cfg))
    stream=stream_class()(cfg)
    # All cached forwards were performed with native preprocessing/autocast.
    # No model weights are changed; heavy prior models are not co-resident with
    # BA buffers on the 8GB GPU.
    import src.motion_filter as motion
    import src.trajectory_filler as filler
    cache=CACHE
    for kind in ['depth','features']:
        receipt=json.loads((cache/f'{kind}_RECEIPT_064.json').read_text())
        if receipt['frames']!=64:raise RuntimeError('Incomplete common prior cache')
        for r in receipt['records']:
            if sha(cache/kind/f'{r["index"]:05d}.npz')!=r['sha256']:raise RuntimeError('Cache identity drift')
    coefficients={}
    def depth(model,index,image,cfg,device,**kwargs):
        with np.load(cache/'depth'/f'{int(index):05d}.npz',allow_pickle=False) as z:
            return torch.from_numpy(z['native_depth'].copy()).to(device)
    def feature(model,index,image,cfg,device,**kwargs):
        with np.load(cache/'features'/f'{int(index):05d}.npz',allow_pickle=False) as z:
            return torch.from_numpy(z['feature'].copy()).to(device)
    for i in range(64):
        with np.load(cache/'depth'/f'{i:05d}.npz',allow_pickle=False) as z:
            c,_=coefficient_map(z['native_depth'],z['flip_depth'][:,::-1],z['native_confidence'],z['tta_valid'],arm_config('A5'))
            coefficients[i]=torch.as_tensor(c[3::8,3::8].copy(),device='cuda',dtype=torch.float32)
    motion.get_metric_depth_estimator=lambda cfg:None
    motion.get_feature_extractor=lambda cfg:None
    motion.predict_metric_depth=depth;motion.predict_img_features=feature
    filler.get_feature_extractor=lambda cfg:None;filler.predict_img_features=feature
    net=DroidNet()
    state=OrderedDict((k.replace('module.',''),v) for k,v in torch.load(cfg['tracking']['pretrained'],map_location='cpu',weights_only=True).items())
    for n in ['update.weight.2.weight','update.weight.2.bias','update.delta.2.weight','update.delta.2.bias']:
        state[n]=state[n][:2]
    net.load_state_dict(state,strict=True);net=net.cuda().eval()
    printer=Printer();video=DepthVideo(cfg,printer)
    video._local_scale_stage='INITIALIZATION'
    extension=load_extension()
    install(video,extension,robust_enabled=a.arm in ['ROBUST','ROBUST_A5'],
        a5_enabled=a.arm in ['A5','ROBUST_A5'],coefficients=coefficients,log_path=out/'BA_CALLS.jsonl',
        endpoint_callback=(lambda args,native,ext:endpoint_check(args,native,ext,out/'ENDPOINT_CHECK.json')) if a.arm=='BASE' else None)
    call=Frontend.__call__;second=Frontend.initialize_second_stage
    def wrapped(front,*args,**kwargs):
        front.video._local_scale_stage=MAIN if front.is_initialized else 'INITIALIZATION'
        return call(front,*args,**kwargs)
    def wrapped_second(front,*args,**kwargs):
        front.video._local_scale_stage='INITIALIZATION_SECOND_STAGE'
        return second(front,*args,**kwargs)
    Frontend.__call__=wrapped;Frontend.initialize_second_stage=wrapped_second
    original_track=motion.MotionFilter.track
    def tracked(filt,index,*args,**kwargs):
        video._local_input_timestamp=int(index)
        if video.counter.value>=cfg['tracking']['buffer']-17:raise RuntimeError('LOCAL_BUFFER_CAPACITY')
        result=original_track(filt,index,*args,**kwargs)
        write(out/'PROGRESS.json',dict(index=int(index),rgb_id=stream.ids[int(index)],keyframes=int(video.counter.value),frames=64))
        print('FRAME',index,'KEYFRAMES',video.counter.value,flush=True)
        return result
    motion.MotionFilter.track=tracked
    fake=types.SimpleNamespace(cfg=cfg,device='cuda:0',droid_net=net,video=video,
        verbose=cfg['verbose'],save_dir=str(out/'native'),printer=printer)
    pathlib.Path(fake.save_dir).mkdir()
    writer=SummaryWriter(str(out/'events'))
    if cfg['mapping']['enable'] or cfg['tracking']['frontend']['enable_online_ba']:
        raise RuntimeError('Local protocol excludes mapping and online global BA')
    tracker=Tracker(fake,Pipe(),writer)
    torch.cuda.reset_peak_memory_stats();started=time.perf_counter()
    tracker.run(stream)
    if not tracker.frontend.is_initialized:
        write(out/'ALGORITHM_FAILURE.json',dict(status='INITIALIZATION_NOT_COMPLETED',keyframes=int(video.counter.value)))
        raise RuntimeError('Native Tracker did not initialize')
    n=int(video.counter.value)
    np.savez_compressed(out/'frontend_state.npz',timestamps=video.timestamp[:n].cpu().numpy(),
        poses_w2c=video.poses[:n].cpu().numpy(),disps=video.disps[:n].cpu().numpy())
    video._local_scale_stage='FINAL_GLOBAL_BA'
    metric=video.metric_depth_reg;video.metric_depth_reg=False
    backend=Backend(net,video,cfg)
    torch.cuda.empty_cache();backend.dense_ba(7,enable_udba=cfg['tracking']['frontend']['enable_opt_dyn_mask'])
    torch.cuda.empty_cache();backend.dense_ba(12,enable_udba=cfg['tracking']['frontend']['enable_opt_dyn_mask'],save_edges_weights=False)
    video.metric_depth_reg=metric
    n=int(video.counter.value)
    np.savez_compressed(out/'keyframe_state.npz',timestamps=video.timestamp[:n].cpu().numpy(),
        poses_w2c=video.poses[:n].cpu().numpy(),disps=video.disps[:n].cpu().numpy(),
        original_mono_disps=video.mono_disps[:n].cpu().numpy(),U=video.uncertainties[:n].cpu().numpy())
    video._local_scale_stage='TRAJECTORY_FILLER'
    fill=PoseTrajectoryFiller(cfg,net,video,printer,device='cuda:0');fill.setup_feature_extractor()
    with torch.no_grad():full,_=fill(stream)
    c2w=full.inv().matrix().cpu().numpy()
    if c2w.shape!=(64,4,4) or not np.isfinite(c2w).all():raise RuntimeError('Incomplete final export')
    np.savez_compressed(out/'trajectory.npz',rgb_ids=stream.ids,c2w=c2w)
    writer.close();torch.cuda.synchronize()
    write(out/'COMPLETE.json',dict(status='COMPLETE',arm=a.arm,frames=64,keyframes=n,
        seconds=time.perf_counter()-started,peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_reserved_bytes=torch.cuda.max_memory_reserved(),trajectory_sha256=sha(out/'trajectory.npz'),
        no_buffer_eviction=True,local_buffer=96,source_commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc'))
    print('ARM_COMPLETE',a.arm,flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        traceback.print_exc();raise
