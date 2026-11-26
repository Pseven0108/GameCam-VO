"""Real cached mask / optical-flow coordinate diagnostic; NOT DROID inference."""
import argparse
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from gamecam.modules.dynamic_prior import DynamicObservationGate,GateConfig,Pi3Cache
from gamecam.modules.dynamic_prior.feature_alignment import ImageGeometry


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache-root',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False);root=Path(args.cache_root)
    cache=Pi3Cache({i:root/'A/predictions'/f'{i:05d}.npz' for i in range(301,333)},(216,384))
    yy,xx=torch.meshgrid(torch.arange(27,device='cuda'),torch.arange(48,device='cuda'),indexing='ij')
    xy=torch.stack([xx,yy],-1).float()[None];weight=torch.ones(1,1,27,48,2,device='cuda')
    rows=[];panels=[];torch.cuda.reset_peak_memory_stats()
    for fid in range(301,332):
        a=cv2.imread(str(root/'original_rgb'/f'{fid:05d}.jpg'));b=cv2.imread(str(root/'original_rgb'/f'{fid+1:05d}.jpg'))
        a=cv2.resize(a,(384,216));b=cv2.resize(b,(384,216))
        flow=cv2.calcOpticalFlowFarneback(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),None,.5,3,15,3,5,1.2,0)
        target=xy+torch.from_numpy(flow[::8,::8]).to('cuda')[None]/8
        mi=cache.batch([fid],'cuda');mj=cache.batch([fid+1],'cuda');g=ImageGeometry((216,384),tuple(mi.shape[-2:]))
        for alpha,beta,floor in [(1,1,.1),(.5,.5,.1),(1,1,0),(2,2,.1)]:
            torch.cuda.synchronize();t=time.perf_counter()
            gated,s=DynamicObservationGate(GateConfig(alpha=alpha,beta=beta,min_gate=floor))(weight,mi,mj,g.feature_to_map(xy),g.feature_to_map(target))
            torch.cuda.synchronize();s.update(rgb_id=fid,alpha=alpha,beta=beta,min_gate=floor,seconds=time.perf_counter()-t)
            rows.append(s)
            if fid in [301,312,325] and (alpha,beta,floor)==(1,1,.1):
                heat=gated[0,0,:,:,0].cpu().numpy();heat=cv2.resize(heat,(384,216));colored=cv2.applyColorMap(np.uint8(255*heat),cv2.COLORMAP_TURBO)
                im=Image.fromarray(cv2.cvtColor(np.hstack([a,colored]),cv2.COLOR_BGR2RGB));ImageDraw.Draw(im).text((5,5),f'RGB{fid} / GPU gate, flow diagnostic',fill='white');panels.append(im)
    (out/'results.json').write_text(json.dumps({'status':'GPU_ADAPTER_DIAGNOSTIC_ONLY','native_droid_ran':False,
        'coordinate_source':'OpenCV Farneback, NOT DROID targets','device':torch.cuda.get_device_name(),
        'rows':rows,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'mask_receipts':cache.receipts},indent=2))
    sheet=Image.new('RGB',(768,216*len(panels)))
    for i,p in enumerate(panels):sheet.paste(p,(0,i*216))
    sheet.save(out/'gpu_gate_diagnostic.jpg',quality=92)
    print('GPU gate diagnostic completed:',len(rows),'edge/config measurements')


if __name__=='__main__':main()
