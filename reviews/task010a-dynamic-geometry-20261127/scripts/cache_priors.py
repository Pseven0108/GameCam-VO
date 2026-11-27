"""Reuse verified TASK009 provider functions on new admitted RGB/K only."""
import argparse
import gc
import importlib.util
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'experiments/TASK010-A'
OLD=Path('D:/aaa/GameCam-VO-TASK009')


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('task009_provider',OLD/'experiments/TASK009/scripts/cache_native_priors.py')
    provider=importlib.util.module_from_spec(spec);spec.loader.exec_module(provider)
    dataset=next(x for x in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()) if x['name']==a.dataset)
    out=TASK/'outputs/priors'/a.dataset;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(43);np.random.seed(43)
    ids=dataset['rgb_ids'];hw=dataset['hw']
    # Pose GT is never opened in this process.
    k=np.load(Path(dataset['rgb_dir']).parent/'intrinsics.npy',allow_pickle=False)
    frames=[]
    for fid in ids:
        raw=cv2.cvtColor(cv2.imread(str(Path(dataset['rgb_dir'])/(f'{fid:05d}'+dataset.get('image_suffix','.jpg')))),cv2.COLOR_BGR2RGB)
        frames.append(torch.from_numpy(cv2.resize(raw,hw[::-1],interpolation=cv2.INTER_LINEAR).copy()).permute(2,0,1)[None].float()/255)
    receipt={'status':'STARTED','rgb_ids':ids,'tracker_hw':hw,'canonical_hw':[392,700],
             'precision':'BF16 autocast; float32 saved','checkpoints':{},'depth':[],'features':[],
             'GT_read_in_inference':False,'rgb_manifest':dataset['rgb_manifest']}
    args=argparse.Namespace(output=out,height=hw[0],width=hw[1],canonical_height=392,canonical_width=700)
    sys.path.insert(0,str(OLD/'external/Metric3D'))
    from hubconf import metric3d_vit_large
    provider.cache_depths(args,ids,frames,k,receipt,metric3d_vit_large)
    (out/'depth_receipt.json').write_text(json.dumps(receipt,indent=2))
    gc.collect();torch.cuda.empty_cache()
    import timm
    model=timm.create_model('vit_small_patch14_reg4_dinov2.lvd142m',pretrained=False,num_classes=0,dynamic_img_size=True,dynamic_img_pad=False)
    checkpoint=provider.WEIGHTS/'dinov2_reg_small_finetuned.pth'
    model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True),strict=True);model.eval().cuda()
    receipt['checkpoints']['fit3d']={'sha256':provider.sha(checkpoint),'strict':True}
    norm=transforms.Normalize([.485,.456,.406],[.229,.224,.225])
    h,w=hw
    for fid,x in zip(ids,frames):
        x=F.interpolate(norm(x),((h//14)*14,(w//14)*14),mode='bilinear',align_corners=False).cuda()
        tic=time.perf_counter()
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            features=model.get_intermediate_layers(x,n=[8,9,10,11],reshape=True,norm=True)[-1][0].permute(1,2,0).float()
        if not torch.isfinite(features).all():raise RuntimeError('Nonfinite FiT3D')
        path=out/f'feature_{fid:05d}.npy';np.save(path,features.cpu().numpy())
        receipt['features'].append({'rgb_id':fid,'shape':list(features.shape),'seconds':time.perf_counter()-tic,'sha256':provider.sha(path)})
    receipt['status']='COMPLETE';(out/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print('COMPLETE',a.dataset,len(ids),flush=True)


if __name__=='__main__':main()
