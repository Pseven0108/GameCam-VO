"""Task 004 runner candidate, based on the sealed Task 003 adapter."""

from task004_controls import policy as task004_policy, require_approved_runtime

require_approved_runtime()

from task003_observer import recorder as task003

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

    out=Path(kw['record_path']).parent.parent
    kw['app_id']=out.parent.parent.name+'_'+out.name

    def connect(*,port,open_browser):
        if port!=9876 or open_browser:
            raise ValueError('unexpected native viewer configuration')
        return None  # approved data-priority file recording; no viewer/network service

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
    native.droid_visualization_rerun(video,**kw)
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

    def task004_begin_filler(self):
        if self.phase is not None or self.seen != len(self) or self.fill_seen != 0:
            raise ValueError('unexpected Filler entry or incomplete tracking')
        self.phase = 'filler'
        progress(self.out,'filler',done=0,n=len(self),keyframes=self.video.counter.value)

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
        from task004c_capture import install,PrefixCaptured
        cached_priors();torch.set_num_threads(2);cv2.setNumThreads(1)
        self.stream.video=self.video;self.stream.rgb_hash=hashlib.sha256();self.stream.phase='tracking'
        import droid_backends
        original=install(self.video,self.stream.out,task004_policy().arm,self.stream)
        try:
            super().tracking(pipe)
        except PrefixCaptured:
            progress(self.stream.out,'captured_before_target_ba',done=self.stream.seen,n=len(self.stream))
            return
        finally:
            droid_backends.ba=original
        raise RuntimeError('PREFIX_EXHAUSTED_WITHOUT_ELIGIBLE_RGB328_BA')

    def terminate(self):
        raise RuntimeError('FINAL_BA_AND_FILLER_NOT_AUTHORIZED_FOR_PREFIX')


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
    import yaml
    yaml_path=Path(os.environ['GAMECAM_TASK003_SEALED_CONFIG'])
    serialized=yaml_path.read_bytes()
    if hashlib.sha256(serialized).hexdigest()!='a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc':
        raise ValueError('historical configuration byte identity mismatch')
    if digest(args.manifest)!='5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537' or [f['rgb_id'] for f in doc['frames']]!=list(range(1,488)):
        raise ValueError('Task 003 is limited to the sealed stride-1 val_007 RGB manifest')
    cfg=yaml.safe_load(serialized)
    if Path(cfg['tracking']['pretrained']).resolve()!=args.weights.resolve():
        raise ValueError('sealed tracker path differs from admitted weight path')
    trace=Path(os.environ['GAMECAM_TASK003_OBSERVER_JSONL'])
    if trace.parent.resolve()!=args.out.resolve() or trace.exists():
        raise ValueError('observation output must be new and belong to this attempt')
    cfg['data'].update(output=str(args.out),input_folder=str(args.manifest.parent))
    active = task004_policy()
    dump(args.out/'task004_policy_receipt.json', dict(arm=active.arm, campaign=active.campaign,
         local_dwu=list(active.local_dwu), final_phases=active.final_phases,
         policy_sha256=os.environ['GAMECAM_TASK004_POLICY_SHA256']))
    setup_seed(cfg['setup_seed'])
    stream=ViperRGB(cfg,args.manifest,args.out)
    stream.frames=stream.frames[:328];stream.ids=stream.ids[:328];stream.color_paths=stream.color_paths[:328];stream.n_img=328
    np.testing.assert_allclose(stream.get_intrinsic().numpy(),doc['output_k'],rtol=0,atol=1.3e-4)
    np.testing.assert_array_equal(stream.get_intrinsic().numpy(),[386.01129150390625, 386.01129150390625, 319.5, 179.5])
    config.save_config(cfg,str(args.out/'native_config.yaml'))
    dump(args.out/'model_input.json',dict(manifest_sha256=digest(args.manifest),actual_loader_k=stream.get_intrinsic().tolist(),
         rgb_ids=stream.ids,stride=1,size=list(OUT),branch=doc['branch'],pose_inputs=0,multiprocessing='spawn'))
    from src.utils import droid_visualization_rerun as vis
    vis.droid_visualization_rerun=native_viewer
    progress(args.out,'model_init',done=0,n=len(stream))
    slam=ObservedSLAM(cfg,stream)
    slam.run()
    capture=load(args.out/'CAPTURE_COMPLETE.json')
    if capture['read_frames']!=328:raise RuntimeError('capture did not process exact prefix')
    progress(args.out,'capture_complete',done=328,n=328,active_count=capture['active_count'])

if __name__=='__main__':
    main()
