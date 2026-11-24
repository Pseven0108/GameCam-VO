"""DROID-W RGB-only VIPER adapter. Upstream tracking, BA and filler are unchanged."""

import argparse
import hashlib
import os
from pathlib import Path
import time

import cv2
import numpy as np
import torch

from run import setup_seed
from src import config
from src.slam import SLAM
from src.utils.datasets import RGB_NoPose
from transfer_common import digest, dump, load
from segment_input import BUFFER, RAW, OUT, checked_manifest, remap_for


def progress(out, phase, **extra):
    dump(out/'progress.json', dict(phase=phase,time_unix=time.time(),**extra))


def cached_priors():
    hub=Path(os.environ['TORCH_HOME'])
    torch.hub.set_dir(str(hub))
    official={'yvanyin/metric3d':'yvanyin_metric3d_main','ywyue/FiT3D':'ywyue_FiT3D_main'}
    original=torch.hub.load

    def load_cached(repo, model, *args, **kw):
        if repo not in official:
            raise ValueError(f'unexpected prior repository: {repo}')
        frozen=hub/official[repo]
        if not (frozen/'hubconf.py').is_file():
            raise FileNotFoundError(frozen/'hubconf.py')
        return original(str(frozen),model,*args,**{**kw,'source':'local'})

    torch.hub.load=load_cached


def native_viewer(video, **kw):
    from src.utils import droid_visualization_rerun as native
    import rerun as rr

    out=Path(kw.pop('record_path')).parent.parent
    kw['app_id']=out.parent.name

    def connect(*,port,open_browser):
        if port!=9876 or open_browser:
            raise ValueError('unexpected native viewer configuration')
        rr.connect_tcp('127.0.0.1:9875',flush_timeout_sec=4.)

    rr.serve_web=connect
    native._to_rr_transform=lambda m: rr.Transform3D(translation=m[:3,3],mat3x3=m[:3,:3])
    original_log=rr.log
    count=0

    def log(path, *args, **kwargs):
        nonlocal count
        if 'timeless' in kwargs:
            kwargs['static']=kwargs.pop('timeless')
        frustum=path.startswith('world/cameras/') and path.endswith('/frustum')
        if path.startswith('world/cameras/') and not frustum:
            # The native frustum points are already in the world frame.
            path=path.replace('world/cameras/','world/camera_transforms/',1)
        if frustum:
            kwargs['strict']=True
        original_log(path,*args,**kwargs)
        if frustum:
            count+=1
            if count==1 or count%32==0:
                dump(out/'native_camera_stream.json',dict(frustum_messages=count,pid=os.getpid()))

    rr.log=log
    native.droid_visualization_rerun(video,record_path=None,**kw)
    if count:
        dump(out/'native_camera_stream.json',dict(frustum_messages=count,pid=os.getpid()))


class ViperRGB(RGB_NoPose):
    def __init__(self,cfg,manifest,out):
        super().__init__(cfg)
        self.doc=checked_manifest(manifest)
        self.frames=self.doc['frames']
        self.ids=[f['rgb_id'] for f in self.frames]
        self.color_paths=[str(manifest.parent/f['file']) for f in self.frames]
        self.n_img=len(self.ids)
        self.out=out
        self.phase=None
        self.seen=0
        self.fill_seen=0
        self.peak=0
        self.fixed=self.doc['branch']=='FIXED_K_NATIVE_RESIZE'

    def get_color(self,index):
        if self.fixed:
            return super().get_color(index)
        image=cv2.imread(self.color_paths[index],cv2.IMREAD_COLOR)
        if image is None or image.shape!=(RAW[1],RAW[0],3):
            raise ValueError('invalid virtual-camera source dimensions')
        src=np.asarray(self.frames[index]['source_k'])
        k=np.asarray(self.doc['output_k'])
        x,y=remap_for(src,k)
        color=cv2.remap(image,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        return (torch.from_numpy(color).float().permute(2,0,1)[[2,1,0]]/255.).unsqueeze(0)

    def __getitem__(self,index):
        if index>=self.n_img:
            raise IndexError(index)
        if self.phase=='tracking':
            n=self.video.counter.value
            self.peak=max(n,self.peak)
            if n>=BUFFER-16:
                raise RuntimeError(f'BUFFER_CAPACITY: tracking {n}/{BUFFER}; reserve 16 filler slots')
            if index!=self.seen:
                raise ValueError('tracking input order mismatch')
        item=super().__getitem__(index)
        ts,color,_,pose=item
        if ts!=index or pose is not None or color.shape!=(1,3,OUT[1],OUT[0]):
            raise ValueError('dataset loader violated tensor or no-pose contract')
        if self.phase=='tracking':
            self.rgb_hash.update(color.numpy().tobytes())
            self.seen+=1
            if index%16==0 or self.seen==len(self):
                progress(self.out,'tracking',done=self.seen,n=len(self),rgb_id=self.ids[index],keyframes=self.peak)
        if self.phase=='filler':
            if index!=self.fill_seen:
                raise ValueError('filler input order mismatch')
            self.fill_seen+=1
            if index%32==0 or self.fill_seen==len(self):
                progress(self.out,'filler',done=self.fill_seen,n=len(self),rgb_id=self.ids[index])
        return item


class ObservedSLAM(SLAM):
    def tracking(self,pipe):
        cached_priors()
        torch.set_num_threads(2)
        cv2.setNumThreads(1)
        self.stream.video=self.video
        self.stream.rgb_hash=hashlib.sha256()
        self.stream.phase='tracking'
        super().tracking(pipe)
        if not self.final_clean or self.stream.seen!=len(self.stream) or self.stream.fill_seen!=len(self.stream):
            raise ValueError('incomplete tracking or filler')
        dump(self.stream.out/'tracking_child_ok.json',dict(pid=os.getpid(),read_frames=self.stream.seen,
             filler_frames=self.stream.fill_seen,scaled_rgb_tensor_sha256=self.stream.rgb_hash.hexdigest(),
             gpu_torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
             gpu_torch_peak_reserved_bytes=torch.cuda.max_memory_reserved()))

    def terminate(self):
        self.stream.phase=None
        if not self.tracker.frontend.is_initialized:
            raise RuntimeError('TRACKING_NEVER_INITIALIZED')
        n=self.video.counter.value
        if n+16>BUFFER:
            raise RuntimeError(f'BUFFER_CAPACITY: filler {n}+16/{BUFFER}')
        indices=self.video.timestamp[:n].cpu().int().tolist()
        if not indices or indices!=sorted(set(indices)) or indices[-1]>=len(self.stream) or indices[0]<0:
            raise ValueError('invalid upstream keyframe index list')
        dump(self.stream.out/'keyframes.json',dict(final_count=n,peak_tracking_count=max(n,self.stream.peak),
             local_indices=indices,rgb_ids=[self.stream.ids[i] for i in indices]))
        super().terminate()

    def backend(self):
        progress(self.stream.out,'final_ba',done=self.stream.seen,n=len(self.stream),keyframes=self.video.counter.value)
        result=super().backend()
        self.stream.phase='filler'
        progress(self.stream.out,'filler',done=0,n=len(self.stream),keyframes=self.video.counter.value)
        return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('out',type=Path)
    parser.add_argument('--weights',type=Path,required=True)
    args=parser.parse_args()
    torch.multiprocessing.set_start_method('spawn')
    cv2.setNumThreads(1)
    torch.set_num_threads(2)
    doc=checked_manifest(args.manifest)
    cfg=config.load_config('./configs/Dynamic/YouTube/youtube.yaml')
    cfg.update(scene='native',dataset='youtube',stride=1,max_frames=-1,droidvis=True,gui=False,save_gt_poses=False)
    cfg['data'].update(output=str(args.out),input_folder=str(args.manifest.parent))
    cfg['tracking'].update(pretrained=str(args.weights),buffer=BUFFER)
    # Upstream scales principal points without the half-pixel term. Supply the inverse
    # of that map so the native projection receives the exact post-resize calibration.
    raw=(np.asarray(doc['output_k'])*3).tolist()
    cfg['cam'].update(H=RAW[1],W=RAW[0],H_out=OUT[1],W_out=OUT[0],H_edge=0,W_edge=0,
                      fx=raw[0],fy=raw[1],cx=raw[2],cy=raw[3])
    cfg['cam'].pop('distortion',None)
    cfg['mapping']['eval_before_final_ba']=False  # Only omit the redundant diagnostic preview.
    if cfg['fast_mode']:
        cfg['mapping']['final_refine_iters']=3000
    if (cfg['mapping']['enable'] or cfg['mapping']['full_resolution'] or
        cfg['tracking']['force_keyframe_every_n_frames']!=-1 or
        cfg['tracking']['uncertainty_params']['gamma_depth']!=.01 or
        not cfg['tracking']['backend']['final_ba'] or not cfg['tracking']['backend']['metric_depth_reg']):
        raise ValueError('upstream YouTube tracking contract changed')
    setup_seed(cfg['setup_seed'])
    stream=ViperRGB(cfg,args.manifest,args.out)
    np.testing.assert_allclose(stream.get_intrinsic().numpy(),doc['output_k'],rtol=0,atol=1.3e-4)
    config.save_config(cfg,str(args.out/'native_config.yaml'))
    dump(args.out/'model_input.json',dict(manifest_sha256=digest(args.manifest),actual_loader_k=stream.get_intrinsic().tolist(),
         rgb_ids=stream.ids,stride=1,size=list(OUT),branch=doc['branch'],pose_inputs=0,multiprocessing='spawn'))
    from src.utils import droid_visualization_rerun as vis
    vis.droid_visualization_rerun=native_viewer
    progress(args.out,'model_init',done=0,n=len(stream))
    slam=ObservedSLAM(cfg,stream)
    slam.run()
    child=load(args.out/'tracking_child_ok.json')
    export=args.out/'native/traj/est_poses_full.txt'
    poses=np.loadtxt(export,ndmin=2)
    if poses.shape!=(len(stream),8) or not np.array_equal(poses[:,0],np.arange(len(stream))):
        raise ValueError('INVALID_POSE_EXPORT upstream integer IDs')
    valid=np.isfinite(poses).all(1)&(np.abs(np.linalg.norm(poses[:,4:],axis=1)-1)<2e-3)
    kf=load(args.out/'keyframes.json')
    dest=args.out/'trajectory.npz'
    np.savez_compressed(dest,rgb_ids=np.asarray(stream.ids),c2w_xyzw=poses[:,1:],valid=valid,
                        keyframe_local_indices=kf['local_indices'],keyframe_rgb_ids=kf['rgb_ids'])
    viewer=load(args.out/'native_camera_stream.json') if (args.out/'native_camera_stream.json').is_file() else {}
    summary=dict(input_frames=len(stream),poses_exported=len(poses),valid_poses=int(valid.sum()),
         trajectory_sha256=digest(dest),upstream_text_sha256=digest(export),keyframes=kf['final_count'],
         peak_tracking_keyframes=kf['peak_tracking_count'],native_viewer_exit=slam.visualizer.exitcode,
         native_camera_messages=viewer.get('frustum_messages',0),native_viewer_pid=slam.visualizer.pid,**child)
    dump(args.out/'model_result.json',summary)
    if not valid.all():
        raise ValueError('INVALID_POSE_EXPORT nonfinite or invalid quaternion')
    progress(args.out,'complete',done=len(stream),n=len(stream),keyframes=kf['final_count'])


if __name__=='__main__':
    main()
