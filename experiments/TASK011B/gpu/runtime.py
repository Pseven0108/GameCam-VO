"""Frozen native runtime helpers. No pose GT is read by this module."""
import hashlib,json,os,sys
from pathlib import Path

TASK=Path(__file__).resolve().parents[1]
FRESH=Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
SOURCE=TASK/'source/DROID-W'
sys.path[:0]=[str(SOURCE),str(FRESH/'source/DROID-W'),str(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'),str(TASK/'scripts')]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.partial')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(path)


def offline_hub():
    import torch
    root=FRESH/'data/torch_hub';torch.hub.set_dir(str(root))
    old=torch.hub.load
    mapping={'yvanyin/metric3d':'yvanyin_metric3d_main','ywyue/FiT3D':'ywyue_FiT3D_main'}
    def load(repo,model,*args,**kwargs):
        if repo not in mapping:raise RuntimeError('Unapproved hub request '+str(repo))
        folder=root/mapping[repo]
        if not (folder/'hubconf.py').exists():raise FileNotFoundError(folder)
        kwargs['source']='local'
        return old(str(folder),model,*args,**kwargs)
    torch.hub.load=load


def inputs(window):
    data=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())
    return next(r for r in data['windows'] if r['window_id']==window)


def config(window,out):
    import yaml
    cfg=yaml.safe_load((TASK/'configs/frozen_r2.yaml').read_text())
    k=inputs(window)['K_640x360']
    cfg['cam'].update(H=1080,W=1920,H_out=360,W_out=640,H_edge=0,W_edge=0,
        fx=k[0]*3,fy=k[1]*3,cx=k[2]*3,cy=k[3]*3)
    cfg.update(scene='native',dataset='youtube',stride=1,max_frames=-1,droidvis=False,gui=False,save_gt_poses=False)
    cfg['data'].update(output=str(out),input_folder=str(out))
    cfg['tracking']['pretrained']=str(FRESH/'data/droid.pth')
    # Recording-only outputs are disabled equally; tracking/math flags unchanged.
    cfg['mono_prior']['save_depth']=False
    cfg['mono_prior']['save_feature']=False
    cfg['mapping']['eval_before_final_ba']=False
    assert cfg['tracking']['buffer']==500 and cfg['tracking']['warmup']==12
    assert cfg['tracking']['uncertainty_params']['gamma_depth']==.01
    assert not cfg['tracking']['frontend']['enable_online_ba'] and not cfg['mapping']['enable']
    return cfg


from src.utils.datasets import RGB_NoPose


class Stream(RGB_NoPose):
    def __init__(self,cfg,window):
        super().__init__(cfg)
        item=inputs(window);self.ids=[x['rgb_id'] for x in item['frames']]
        self.color_paths=[str(FRESH/'data'/item['sequence']/f'{f:05d}.jpg') for f in self.ids]
        self.n_img=len(self.ids)
        import numpy as np
        np.testing.assert_allclose(self.get_intrinsic().cpu().numpy(),item['K_640x360'],atol=5e-5,rtol=0)
        for path,info in zip(self.color_paths,item['frames']):
            if Path(path).stat().st_size!=info['bytes'] or sha(path)!=info['sha256']:
                raise RuntimeError('Remote original JPEG identity mismatch '+path)


def stream_class():return Stream
