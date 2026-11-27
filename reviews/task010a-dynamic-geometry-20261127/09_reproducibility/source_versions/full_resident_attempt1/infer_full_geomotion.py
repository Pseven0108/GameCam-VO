"""Full GeoMotion raw detector, official recurrent RAFT features, no SAM refinement."""
import argparse
import ast
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from types import SimpleNamespace
import cv2
import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms.functional as TVF
from torchvision.models.optical_flow import raft_large
from torchvision.models.optical_flow.raft import make_coords_grid
from infer_candidates import empty_parameters,read_inputs,save_prediction,TASK,EXT,WEIGHT


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--limit',type=int,default=0)
    p.add_argument('--output-suffix',default='');a=p.parse_args()
    ds=next(d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()) if d['name']==a.dataset)
    out=TASK/'outputs/geomotion_full'/(a.dataset+a.output_suffix);out.mkdir(parents=True,exist_ok=False)
    receipt={'status':'STARTED','dataset':a.dataset,'model':'Full_GeoMotion_raw_detector','SAM2_refinement':False,
             'temporal_context':4,'pixel_limit':255000,'GT_loaded':False,'encoder_timings':[],'frames':[]}
    torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(43);np.random.seed(43)
    start=time.perf_counter()
    try:
        source=EXT/'GeoMotion';frames,_=read_inputs(ds,255000);ids=ds['rgb_ids']
        stop=a.limit or len(ids);context_stop=min(len(ids),(stop+3)//4*4)
        # Execute ONLY two verbatim upstream helper definitions, with explicit
        # model/transforms globals; avoid importing the unused SAM2/demo stack.
        path=source/'motion_seg_inference_raft.py';text=path.read_text(encoding='utf-8')
        tree=ast.parse(text);nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ['_run_raft_get_hidden','_fuse_hidden_states']]
        if len(nodes)!=2:raise RuntimeError('Upstream RAFT feature helpers changed')
        raft=raft_large(weights=None,progress=False)
        raft.load_state_dict(torch.load(WEIGHT/'raft_large.pth',map_location='cpu',weights_only=True),strict=True)
        raft.cuda().eval();provider=SimpleNamespace(RAFT_MODEL=raft,RAFT_TRANSFORMS=lambda x,y:(x*2-1,y*2-1))
        ns={'torch':torch,'F_nn':F,'F_vision':TVF,'make_coords_grid':make_coords_grid,'msi':provider}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
        receipt['RAFT_helper_source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        h,w=frames[0].shape[-2:];hh=(h+7)//8*8;ww=(w+7)//8*8
        features={}
        for chunk in range(0,context_stop,4):
            context=list(range(chunk,min(chunk+4,len(ids))))
            forward=[];backward=[]
            tic=time.perf_counter();torch.cuda.reset_peak_memory_stats()
            with torch.inference_mode():
                for u,v in zip(context[:-1],context[1:]):
                    f=ns['_run_raft_get_hidden'](frames[u].cuda(),frames[v].cuda(),h,w,hh,ww,12)
                    if chunk==0 and u==0:
                        captured=[]
                        hook=raft.update_block.register_forward_hook(lambda _m,_a,result:captured.append(result[0].detach().cpu()))
                        try:
                            x=TVF.resize(frames[u][None].cuda(),[hh,ww],antialias=False)*2-1
                            y=TVF.resize(frames[v][None].cuda(),[hh,ww],antialias=False)*2-1
                            raft(x,y,num_flow_updates=12)
                        finally:hook.remove()
                        reference=captured[-1][0]
                        difference=(reference-f.cpu()).abs()
                        equal=torch.allclose(reference,f.cpu(),atol=1e-5,rtol=1e-4)
                        receipt['RAFT_native_hidden_equivalence']={'max_abs':float(difference.max()),
                            'atol':1e-5,'rtol':1e-4,'PASS':bool(equal),'source_rgb':ids[u],'target_rgb':ids[v]}
                        if not equal:raise RuntimeError('Official helper does not reproduce native torchvision RAFT state')
                        del captured,reference,difference,x,y
                    b=ns['_run_raft_get_hidden'](frames[v].cuda(),frames[u].cuda(),h,w,hh,ww,12)
                    forward.append(f.cpu());backward.append(b.cpu());del f,b
            for local,index in enumerate(context):
                evidence=[]
                if local>0:evidence.append(backward[local-1])
                if local<len(context)-1:evidence.append(forward[local])
                if not evidence:raise RuntimeError('Missing recurrent features')
                features[index]=torch.stack(evidence).mean(0)
            receipt['encoder_timings'].append({'context':[ids[t] for t in context],
                'raft_seconds':time.perf_counter()-tic,'peak_allocated_bytes':torch.cuda.max_memory_allocated()})
            print('FULL_RAFT',ds['name'],chunk,flush=True)
        provider.RAFT_MODEL=None;raft.cpu();del raft;gc.collect();torch.cuda.empty_cache()
        sys.path.insert(0,str(source))
        from pi3.models.pi3_conf_flow_cam_lowfeature_wo_mean_raft import create_pi3_motion_segmentation_model
        with empty_parameters():model=create_pi3_motion_segmentation_model(pi3_model_path=None)
        state=torch.load(WEIGHT/'geomotion_full.pth',map_location='cpu',weights_only=True,mmap=True)
        model.load_state_dict(state['model_state_dict'],strict=True,assign=True);del state
        model.cuda().eval();receipt['strict_model_load']=True
        for chunk in range(0,context_stop,4):
            context=list(range(chunk,min(chunk+4,len(ids))))
            x=torch.stack([frames[t] for t in context])[None].cuda()
            feature=torch.stack([features[t] for t in context])[None].cuda()
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):pred=model(x,raft_features=feature)
            torch.cuda.synchronize();elapsed=time.perf_counter()-tic
            for local,index in enumerate(context):
                if index>=stop:break
                row=save_prediction(out,ids[index],[ids[t] for t in context],pred['motion_mask'][0,local],
                    pred['conf'][0,local,:,:,0],pred['local_points'][0,local,:,:,2])
                row.update(chunk_seconds=elapsed,peak_allocated_bytes=torch.cuda.max_memory_allocated())
                receipt['frames'].append(row);print('FULL_DONE',ds['name'],ids[index],row,flush=True)
            del x,feature,pred
        receipt.update(status='COMPLETE',total_seconds=time.perf_counter()-start)
    except Exception:
        receipt.update(status='FAILED',traceback=traceback.format_exc(),total_seconds=time.perf_counter()-start)
        raise
    finally:(out/'receipt.json').write_text(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
