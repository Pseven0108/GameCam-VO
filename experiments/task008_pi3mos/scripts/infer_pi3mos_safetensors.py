"""Frozen Pi3MOS forward only, sequential three-/five-frame Night007 inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

from preprocess import read_rgb,contract_check
from visualize_masks import save_views


def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--checkpoint',required=True);args=p.parse_args()
    c=json.loads(Path(args.config).read_text());w=Path(c['remote_output']);out=w/'outputs/night007';out.mkdir(parents=True,exist_ok=False)
    state={'stage':'STARTING','completed_A':0,'completed_B':0,'model_forwards_started':0,'model_forwards_complete':0,'auto_retry':False}
    def status(): (w/'INFERENCE_STATE.json').write_text(json.dumps(state,indent=2)+'\n')
    status()
    try:
        source=Path(c['model_source_outside_project'])
        assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==c['source_commit']
        assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()
        assert torch.cuda.is_available() and '3090' in torch.cuda.get_device_name(0)
        assert torch.cuda.is_bf16_supported(),'BF16 unsupported; stop before running rather than silently changing precision'
        assert torch.cuda.mem_get_info()[0]>20*1024**3,'GPU memory no longer free for this task'
        random.seed(43);np.random.seed(43);torch.manual_seed(43);torch.cuda.manual_seed_all(43)
        state['stage']='LOADING_OFFICIAL_WEIGHT';status()
        sys.path.insert(0,str(source));from pi3.models.pi3 import Pi3
        checkpoint=Path(args.checkpoint);h=hashlib.sha256()
        with checkpoint.open('rb') as f:
            for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
        load_start=time.perf_counter()
        model=Pi3()
        # Official download has a safetensors header despite our initial .pth name.
        # Validate the binary format; do not fall back to unrestricted pickle.
        import struct
        with checkpoint.open('rb') as sf:
            header_bytes=struct.unpack('<Q',sf.read(8))[0]
            assert 0<header_bytes<4*1024**2
            header=json.loads(sf.read(header_bytes))
        assert len(header)==1276 and all('data_offsets' in x for x in header.values())
        assert max(x['data_offsets'][1] for x in header.values())==checkpoint.stat().st_size-header_bytes-8
        from safetensors.torch import load_file
        weight=load_file(str(checkpoint),device='cpu')
        assert isinstance(weight,dict) and weight,'Expected official plain state_dict'
        loaded=model.load_state_dict(weight,strict=True)
        assert not loaded.missing_keys and not loaded.unexpected_keys
        del weight
        model=model.cuda().eval()
        dump(w/'WEIGHT_LOAD_RECEIPT.json',{'source_commit':c['source_commit'],'official_file_id':c['official_weight_file_id'],
             'checkpoint_path':str(checkpoint),'checkpoint_bytes':checkpoint.stat().st_size,'sha256':h.hexdigest(),
             'binary_format':'safetensors','header_tensor_count':len(header),'strict':True,'missing_keys':loaded.missing_keys,'unexpected_keys':loaded.unexpected_keys,
             'parameters':sum(x.numel() for x in model.parameters()),'parameter_dtype':str(next(model.parameters()).dtype),
             'load_seconds':time.perf_counter()-load_start,'random_weights_used_for_forward':False,
             'torch':torch.__version__,'CUDA_build':torch.version.cuda,'GPU':torch.cuda.get_device_name(0),
             'autocast':'bfloat16','inference_mode':True,'RoPE_implementation_module':model.rope.__class__.__module__,
             'DINO_xformers':'Optional upstream fallback; not required by this adapter'})
        contracts=contract_check();cache={};mappings=[]
        before=json.loads((w/'INPUT_IDENTITY_BEFORE.json').read_text());ident={x['rgb_id']:x for x in before['frames']}
        for fid in range(c['context_source_first_rgb_id'],c['context_source_last_rgb_id']+1):
            r=ident[fid];b=Path(r['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256']
            a,m=read_rgb(r['path'],c['pixel_limit']);cache[fid]=torch.from_numpy(a);mappings.append({'rgb_id':fid,**m})
        assert all(m['model_wh']==c['expected_model_wh'] and m['original_wh']==c['expected_raw_wh'] for m in mappings)
        dump(w/'PREPROCESS_VERIFICATION.json',{'contracts':contracts,'mappings':mappings,'ImageNet_normalized_in_adapter':False,
             'uint8_BGR_DPVO_stream_used':False,'images_verified':len(cache)})
        rgb_out=out/'original_rgb';rgb_out.mkdir()
        for fid in range(c['target_first_rgb_id'],c['target_last_rgb_id']+1):shutil.copyfile(ident[fid]['path'],rgb_out/f'{fid:05d}.jpg')
        manifests=[];all_stats=[];shapes_written=False
        for mode in c['execution_order']:
            state['stage']='RUNNING_'+mode;status();dest=out/mode;dest.mkdir();(dest/'predictions').mkdir()
            offsets=c[mode+'_offsets'];last_prob=None
            for fid in range(c['target_first_rgb_id'],c['target_last_rgb_id']+1):
                if shutil.disk_usage(w).free<2*1024**3:raise RuntimeError('Task008 data volume below2GiB safety reserve')
                tic=time.perf_counter();ids=[fid+d for d in offsets]
                batch=torch.stack([cache[x] for x in ids])[None].cuda()
                torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
                start,end=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
                state['model_forwards_started']+=1;state['current_mode']=mode;state['current_rgb_id']=fid;status()
                forward_start=time.perf_counter();start.record()
                with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):pred=model(batch)
                end.record();torch.cuda.synchronize();forward_wall=time.perf_counter()-forward_start
                n=len(ids);hh,ww=c['expected_model_wh'][1],c['expected_model_wh'][0]
                assert pred['dynamic_masks'].shape==(1,n,1,hh,ww,1)
                assert pred['conf'].shape==(1,n,hh,ww,1) and pred['local_points'].shape==(1,n,hh,ww,3)
                assert pred['camera_poses'].shape==(1,n,4,4)
                for key,x in pred.items():
                    if torch.is_tensor(x) and not bool(torch.isfinite(x).all()):raise RuntimeError('Nonfinite original model output: '+key)
                if not shapes_written:
                    dump(w/'MODEL_INTERFACE_RECEIPT.json',{'input_shape':list(batch.shape),'input_dtype':str(batch.dtype),
                         'input_range':[float(batch.min()),float(batch.max())],
                         'outputs':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in pred.items()},
                         'dynamic_extraction':'dynamic_masks[0,:,0,:,:,0] -> [N,H,W]; save last only',
                         'confidence_already_sigmoid':True,'dynamic_already_sigmoid':True,
                         'DPVO_or_DROID_imported':any(k=='dpvo' or k.startswith('dpvo.') or k=='droid' for k in sys.modules)})
                    shapes_written=True
                prob=pred['dynamic_masks'][0,-1,0,:,:,0].float().cpu()
                conf=pred['conf'][0,-1,:,:,0].float().cpu().numpy()
                points=pred['local_points'][0,-1].float().cpu().numpy();depth=points[...,2]
                pose=pred['camera_poses'][0,-1].float().cpu().numpy()
                assert prob.min()>=0 and prob.max()<=1 and conf.min()>=0 and conf.max()<=1 and (depth>0).all()
                original=F.interpolate(prob[None,None],size=(c['expected_raw_wh'][1],c['expected_raw_wh'][0]),mode='bilinear',align_corners=False)[0,0].numpy()
                model_prob=prob.numpy()
                prediction=dest/'predictions'/f'{fid:05d}.npz'
                np.savez_compressed(prediction,dynamic_probability_model=model_prob,dynamic_probability_original=original,
                                    confidence_model=conf,depth_model=depth,local_points_last=points,camera_pose_last=pose,
                                    context_rgb_ids=np.asarray(ids,np.int32),target_rgb_id=np.int32(fid))
                vis=save_views(ident[fid]['path'],original,conf,depth,dest,fid,c['reference_dynamic_threshold'])
                r={'mode':mode,'target_rgb_id':fid,'context_rgb_ids':ids,'input_shape':list(batch.shape),
                   'forward_GPU_ms':float(start.elapsed_time(end)),'forward_wall_seconds':forward_wall,
                   'GPU_peak_allocated_bytes':torch.cuda.max_memory_allocated(),'GPU_peak_reserved_bytes':torch.cuda.max_memory_reserved(),
                   'model_probability_mean':float(model_prob.mean()),'model_probability_quantiles':np.quantile(model_prob,[0,.5,.9,.95,1]).tolist(),
                   'confidence_mean':float(conf.mean()),'confidence_quantiles':np.quantile(conf,[0,.1,.5,.9,.95,1]).tolist(),
                   'dynamic_original_area':{str(t):float((original>t).mean()) for t in c['thresholds']},
                   'dynamic_model_area':{str(t):float((model_prob>t).mean()) for t in c['thresholds']},
                   'depth_units':'nonmetric auxiliary only','depth_display':vis,
                   'Eulerian_temporal_probability_MAD':None if last_prob is None else float(np.abs(model_prob-last_prob).mean()),
                   'Eulerian_temporal_mask_IoU':None,'GT_detection_accuracy':None,
                   'prediction_sha256':hashlib.sha256(prediction.read_bytes()).hexdigest(),'prediction_bytes':prediction.stat().st_size}
                if last_prob is not None:
                    a,b=model_prob>.4,last_prob>.4;union=(a|b).sum();r['Eulerian_temporal_mask_IoU']=float((a&b).sum()/union) if union else None
                last_prob=model_prob.copy();r['per_target_wall_with_saving_seconds']=time.perf_counter()-tic
                with (dest/'statistics.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r,allow_nan=False)+'\n');f.flush()
                manifests.append({'mode':mode,'target_rgb_id':fid,'input_ids':ids,'inputs':[ident[x] for x in ids],
                                  'output_prediction':str(prediction),'sha256':r['prediction_sha256'],'bytes':r['prediction_bytes']})
                all_stats.append(r);state['completed_'+mode]+=1;state['model_forwards_complete']+=1;status()
                del pred,batch,prob
                print(json.dumps({'mode':mode,'rgb_id':fid,'done':state['model_forwards_complete'],'GPU_ms':r['forward_GPU_ms'],
                                  'peak_GiB':r['GPU_peak_allocated_bytes']/1024**3,'dynamic_area_p04':r['dynamic_original_area']['0.4']}),flush=True)
            dump(dest/'MODE_COMPLETE.json',{'mode':mode,'targets':32,'output_frames':list(range(301,333)),'continuous_predictions_saved':True})
        dump(w/'INFERENCE_INPUT_OUTPUT_MANIFEST.json',{'records':manifests,'GT_used':False,'original_frame_IDs_preserved':True})
        dump(w/'INFERENCE_STATISTICS.json',{'frames':all_stats,'total_forward_count':len(all_stats),'accuracy_or_GT_IoU_computed':False,
             'temporal_metric_limit':'Eulerian same-pixel proxies; camera/object motion affects them; not detection accuracy or motion-compensated consistency'})
        assert state['completed_A']==state['completed_B']==32
        state['stage']='COMPLETE_A_B_INFERENCE';status()
    except Exception as e:
        state['stage']='STOPPED_ERROR';state['error_type']=type(e).__name__;state['error']=str(e);status();raise


if __name__=='__main__':main()
