"""Isolated local runtime; has no SSH/network or offline GT reader."""
import hashlib,json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
TASK=ROOT/'candidate'
SOURCE=ROOT/'upstream/DROID-W'
OLD=pathlib.Path('/mnt/d/aaa/GameCam-VO/baselines/droid_w/upstream')
ASSETS=pathlib.Path('/mnt/d/aaa/GameCam-VO/data/sota_assets/DROID_W')
DEPENDENCIES=OLD.parent/'prior_sources'
sys.path[:0]=[str(TASK/'src'),str(SOURCE),str(OLD),
    '/mnt/d/aaa/GameCam-VO-TASK011B/experiments/TASK011B/CADP_DR_EXPERIMENTAL_BRANCH',
    '/mnt/d/aaa/GameCam-VO-TASK011B/experiments/TASK011B/scripts']
# Reuse only read-only third-party packages. The audited source's own Python
# files are always imported from the exported c3414af6 tree.
import types
third=types.ModuleType('thirdparty');third.__path__=[str(OLD/'thirdparty')]
sys.modules.setdefault('thirdparty',third)

DATA=TASK/'data/train_004_01658-01721'
CACHE=TASK/'cache/train_004_01658-01721'
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for x in iter(lambda:f.read(4*1024**2),b''):h.update(x)
    return h.hexdigest()
def write(path,value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def manifest():return json.loads((DATA/'INPUT_MANIFEST.json').read_text())
def config(out):
    import yaml
    cfg=yaml.safe_load(pathlib.Path('/mnt/d/aaa/GameCam-VO-TASK011B/experiments/TASK011B/configs/frozen_r2.yaml').read_text())
    k=manifest()['K_640x360']
    cfg['cam'].update(H=1080,W=1920,H_out=360,W_out=640,H_edge=0,W_edge=0,
        fx=k[0]*3,fy=k[1]*3,cx=k[2]*3,cy=k[3]*3)
    cfg.update(scene='native',dataset='youtube',stride=1,max_frames=-1,
        droidvis=False,gui=False,save_gt_poses=False,setup_seed=43)
    cfg['data'].update(output=str(out),input_folder=str(DATA/'rgb'))
    cfg['tracking']['pretrained']=str(ASSETS/'weights/droid.pth')
    # 64 frames cannot exhaust 96 slots. This common local capacity reduces
    # allocation only; no overwrite, eviction or per-arm buffer differences.
    cfg['tracking']['buffer']=96
    cfg['tracking']['uncertainty_params']['visualize']=False
    cfg['mono_prior'].update(save_depth=False,save_feature=False)
    cfg['mapping']['eval_before_final_ba']=False
    return cfg
def offline_hub():
    import torch
    torch.hub.set_dir(str(ASSETS/'torch_home/hub'))
    original=torch.hub.load
    def local(repo,model,*args,**kwargs):
        paths={'yvanyin/metric3d':DEPENDENCIES/'Metric3D','ywyue/FiT3D':DEPENDENCIES/'FiT3D'}
        if repo not in paths:raise RuntimeError('Unapproved hub request '+str(repo))
        if repo=='ywyue/FiT3D':
            # Official hubconf first downloads a timm backbone, then overwrites
            # its complete state with this fine-tuned checkpoint. Avoid that
            # redundant network download; strict loading verifies every key.
            if model!='dinov2_reg_small_fine':raise RuntimeError('Unapproved FiT3D model')
            import timm
            net=timm.create_model('vit_small_patch14_reg4_dinov2.lvd142m',
                pretrained=False,num_classes=0,dynamic_img_size=True,dynamic_img_pad=False)
            state=torch.load(ASSETS/'torch_home/hub/checkpoints/dinov2_reg_small_finetuned.pth',
                map_location='cpu',weights_only=True)
            receipt=net.load_state_dict(state,strict=True)
            print('LOCAL_FIT3D_STRICT_LOAD',receipt,flush=True)
            return net
        kwargs['source']='local';return original(str(paths[repo]),model,*args,**kwargs)
    torch.hub.load=local

def compatible_metric_attention():
    """Only replace the incompatible optional xFormers fused attention call.

    PyTorch SDPA implements the same scaled dot-product attention. Weights,
    token shapes, normalization and preprocessing are unchanged. This is a
    declared local numerical backend deviation, never a formal equivalence
    claim to the server's cu118 implementation.
    """
    import torch
    import torch.nn.functional as F
    found=[]
    def attention(q,k,v,attn_bias=None,**kwargs):
        if attn_bias is not None and not isinstance(attn_bias,torch.Tensor):
            raise RuntimeError('Unsupported non-tensor attention mask')
        out=F.scaled_dot_product_attention(q.transpose(1,2),k.transpose(1,2),v.transpose(1,2),
            attn_mask=attn_bias,dropout_p=0.,is_causal=False)
        return out.transpose(1,2)
    for name,module in list(sys.modules.items()):
        if name.endswith(('ViT_DINO','ViT_DINO_reg')) and hasattr(module,'memory_efficient_attention'):
            module.memory_efficient_attention=attention;found.append(name)
    if not found:raise RuntimeError('Expected Metric3D attention module was not imported')
    return found

def stream_class():
    from src.utils.datasets import RGB_NoPose
    class Stream(RGB_NoPose):
        def __init__(self,cfg):
            super().__init__(cfg)
            self.info=manifest();self.ids=[f['rgb_id'] for f in self.info['frames']]
            self.color_paths=[str(DATA/'rgb'/f['filename']) for f in self.info['frames']]
            self.n_img=len(self.color_paths)
            import numpy as np
            np.testing.assert_allclose(self.get_intrinsic().cpu().numpy(),self.info['K_640x360'],atol=5e-5,rtol=0)
            for p,f in zip(self.color_paths,self.info['frames']):
                if sha(p)!=f['sha256']:raise RuntimeError('JPEG identity drift')
    return Stream
