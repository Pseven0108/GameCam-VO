"""Official LEAP kernel only; no VO backend and no model-code redistribution."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np
from PIL import Image,ImageDraw
import torch
from omegaconf import OmegaConf

ROOT=Path(__file__).resolve().parents[3]
RGB=Path(r'D:\aaa\GameCam-VO\experiments\task008_pi3mos\retrieved\outputs\night007\original_rgb')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,default=16);p.add_argument('--height',type=int,default=128)
    p.add_argument('--width',type=int,default=224);p.add_argument('--grid',type=int,default=8)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    receipt={'status':'STARTED','whole_leapvo_ran':False,'droid_integration':False,'gt_available':False}
    try:
        sys.path.insert(0,str(ROOT/'external/LEAP-VO/main'))
        from leap.leap_kernel import LeapKernel
        cfg=OmegaConf.load(ROOT/'external/LEAP-VO/configs/demo.yaml')
        model=LeapKernel(cfg)
        weights=ROOT/'external/weights/leap_kernel.pth'
        state=torch.load(weights,map_location='cpu',weights_only=True)
        receipt['checkpoint_top_level_keys']=list(state)[:8]
        if 'state_dict' in state:state=state['state_dict']
        model.load_state_dict(state,strict=True)
        model.eval().cuda()
        torch.set_num_threads(2);torch.manual_seed(43);torch.cuda.manual_seed_all(43)
        ids=list(range(301,301+a.frames))
        images=[np.asarray(Image.open(RGB/f'{i:05d}.jpg').convert('RGB').resize((a.width,a.height),Image.Resampling.BILINEAR)).copy() for i in ids]
        x=torch.from_numpy(np.stack(images)).permute(0,3,1,2).float()[None].cuda()
        yy,xx=torch.meshgrid(torch.linspace(12,a.height-13,a.grid,device='cuda'),torch.linspace(12,a.width-13,a.grid,device='cuda'),indexing='ij')
        xy=torch.stack([xx.flatten(),yy.flatten()],-1)
        queries=torch.cat([torch.zeros(len(xy),1,device='cuda'),xy],-1)[None]
        torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
        with torch.inference_mode():
            tracks,_,visibility,(cov_x,cov_y),dynamic,_=model(x,queries,iters=4)
        torch.cuda.synchronize()
        elapsed=time.perf_counter()-start
        arrays={k:v.float().cpu().numpy() for k,v in [('tracks',tracks),('visibility',visibility),('cov_x',cov_x),('cov_y',cov_y),('dynamic_probability',dynamic)]}
        if not all(np.isfinite(v).all() for v in arrays.values()):raise ValueError('Nonfinite LEAP output')
        np.savez_compressed(a.output/'predictions.npz',**arrays,rgb_ids=ids)
        receipt.update(status='INDEPENDENT_LEAP_INFERENCE_COMPLETE',strict_load=True,frames=len(ids),
            input_hw=[a.height,a.width],queries=len(xy),precision='FP32',seconds=elapsed,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            checkpoint_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
            gpu=torch.cuda.get_device_name(),torch=torch.__version__,
            outputs={k:{'shape':list(v.shape),'min':float(v.min()),'median':float(np.median(v)),'max':float(v.max())} for k,v in arrays.items()})
        panels=[]
        for t in (0,len(ids)//2,len(ids)-1):
            im=Image.fromarray(images[t]);draw=ImageDraw.Draw(im)
            for j,(u,v) in enumerate(arrays['tracks'][0,t]):
                if arrays['visibility'][0,t,j]<.9:continue
                color=(255,60,50) if arrays['dynamic_probability'][0,t,j]>.4 else (40,255,70)
                draw.ellipse((u-2,v-2,u+2,v+2),fill=color)
            draw.text((5,5),f'LEAP / RGB{ids[t]}',fill='white');panels.append(im)
        sheet=Image.new('RGB',(a.width*len(panels),a.height))
        for i,im in enumerate(panels):sheet.paste(im,(i*a.width,0))
        sheet.save(a.output/'contact_sheet.jpg',quality=90)
    except BaseException as error:
        receipt.update(status='FAILED',error=str(error),traceback=traceback.format_exc());raise
    finally:
        (a.output/'statistics.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
