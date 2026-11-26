"""Isolated Easi3R attention-mask research, without RAFT/SAM2/global BA.

Only the official external source is imported/executed. Noncommercial model
code and weights remain outside the published core. Three images and every
directed pair supply at least two samples to each official std aggregation.
"""
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

import numpy as np
from PIL import Image, ImageDraw
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.cluster import KMeans
from skimage.filters import threshold_multiotsu

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'external/Easi3R'
RGB=Path(r'D:\aaa\GameCam-VO\experiments\task008_pi3mos\retrieved\outputs\night007\original_rgb')


def original_functions():
    """Execute selected unchanged AST nodes, excluding unrelated imports."""
    namespace=dict(torch=torch,nn=nn,np=np,KMeans=KMeans,threshold_multiotsu=threshold_multiotsu)
    commons=SOURCE/'dust3r/cloud_opt/commons.py'
    base=SOURCE/'dust3r/cloud_opt/base_opt.py'
    nodes=[x for x in ast.parse(commons.read_text(encoding='utf-8')).body if isinstance(x,ast.FunctionDef) and x.name=='NoGradParamDict']
    tree=ast.parse(base.read_text(encoding='utf-8'))
    nodes += [x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('cluster_attention_maps','adaptive_multiotsu_variance')]
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='BasePCOptimizer')
    nodes += [x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='aggregate_attention_maps']
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(base),'exec'),namespace)
    return namespace


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--height',type=int,default=128);p.add_argument('--width',type=int,default=224)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='STARTED',full_easi3r_pipeline=False,raft_used=False,sam2_used=False,
                 global_optimization=False,droid_integration=False,dynamic_gt_available=False)
    try:
        if a.height%16 or a.width%16:raise ValueError('DUSt3R patch divisibility')
        torch.set_num_threads(2);torch.manual_seed(43);np.random.seed(43);torch.cuda.manual_seed_all(43)
        sys.path.insert(0,str(SOURCE))
        from dust3r.model import AsymmetricCroCo3DStereo
        checkpoint=ROOT/'external/weights/DUSt3R_ViTLarge_BaseDecoder_512_dpt.pth'
        with torch.serialization.safe_globals([argparse.Namespace]):
            saved=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
        expression=saved['args'].model.replace('ManyAR_PatchEmbed','PatchEmbedDust3R')
        parsed=ast.parse(expression,mode='eval').body
        if not isinstance(parsed,ast.Call) or not isinstance(parsed.func,ast.Name) or parsed.func.id!='AsymmetricCroCo3DStereo':
            raise ValueError('Unexpected official checkpoint constructor')
        # The constructor string is recorded, but arbitrary names/calls are not accepted.
        for node in ast.walk(parsed):
            if isinstance(node,ast.Call) and node is not parsed:raise ValueError('Nested checkpoint constructor call')
            if isinstance(node,ast.Name) and node.id not in ('AsymmetricCroCo3DStereo','inf'):raise ValueError('Unexpected constructor name')
        model=eval(compile(ast.Expression(parsed),'<official-checkpoint-constructor>','eval'),
                   {'__builtins__':{},'AsymmetricCroCo3DStereo':AsymmetricCroCo3DStereo,'inf':float('inf')})
        model.load_state_dict(saved['model'],strict=True)
        receipt.update(strict_load=True,checkpoint_constructor=expression)
        del saved;gc.collect()
        model=model.eval().cuda()
        ids=[301,312,325]
        raw=[np.array(Image.open(RGB/f'{i:05d}.jpg').convert('RGB').resize((a.width,a.height),Image.Resampling.BILINEAR),copy=True) for i in ids]
        tensors=[torch.from_numpy(x).permute(2,0,1).float()[None].cuda()/127.5-1 for x in raw]
        views=[dict(img=x,true_shape=torch.tensor([[a.height,a.width]],device='cuda'),instance=str(i)) for i,x in enumerate(tensors)]
        edges=[(i,j) for i in range(3) for j in range(3) if i!=j]
        pred1={k:[] for k in ('cross_atten_maps_k','match_feature')};pred2={'cross_atten_maps_k':[]}
        pair_stats=[];torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
        with torch.inference_mode():
            for i,j in edges:
                t=time.perf_counter()
                with torch.autocast('cuda',dtype=torch.bfloat16):r1,r2=model(views[i],views[j])
                torch.cuda.synchronize()
                for key in pred1:pred1[key].append(r1[key][0].float().cpu())
                pred2['cross_atten_maps_k'].append(r2['cross_atten_maps_k'][0].float().cpu())
                pair_stats.append(dict(source=ids[i],target=ids[j],seconds=time.perf_counter()-t,
                    output_shapes={k:list(v.shape) for k,v in r1.items()},finite=all(bool(torch.isfinite(v).all()) for v in [*r1.values(),*r2.values()])))
                del r1,r2
        torch.cuda.synchronize();forward_seconds=time.perf_counter()-start
        ns=original_functions()
        context=SimpleNamespace(str_edges=[f'{i}_{j}' for i,j in edges],imshapes=[(a.height,a.width)]*3)
        maps=ns['aggregate_attention_maps'](context,pred1,pred2)
        def fuse(x):
            normalized=(x-x.min())/(x.max()-x.min()+1e-6)
            fused=normalized.mean(-1)
            return (fused-fused.min())/(fused.max()-fused.min()+1e-6)
        im,iv,jm,jv=map(fuse,maps)
        dynamic=(1-im)*iv*jm*(1-jv)
        lo=dynamic.amin((1,2),keepdim=True);hi=dynamic.amax((1,2),keepdim=True)
        dynamic=(dynamic-lo)/(hi-lo+1e-6)
        features=[None]*3
        for (i,j),value in zip(edges,pred1['match_feature']):features[i]=value
        refined,labels=ns['cluster_attention_maps'](torch.stack(features),dynamic,n_clusters=64)
        up=F.interpolate(refined[:,None],size=(a.height,a.width),mode='bilinear',align_corners=False)[:,0]
        threshold=float(ns['adaptive_multiotsu_variance'](up.numpy()))
        masks=up>threshold
        if not torch.isfinite(up).all():raise ValueError('Nonfinite attention mask')
        np.savez_compressed(a.output/'attention_predictions.npz',rgb_ids=ids,dynamic_score=up.numpy(),
            patch_dynamic_score=dynamic.numpy(),refined_patch_score=refined.numpy(),cluster_labels=labels.numpy(),binary_mask=masks.numpy())
        panels=[]
        for n,image in enumerate(raw):
            overlay=image.astype(np.float32);mask=masks[n].numpy()
            overlay[mask]=.6*overlay[mask]+.4*np.array([255,30,20])
            im=Image.fromarray(overlay.astype(np.uint8));ImageDraw.Draw(im).text((4,4),f'Easi attention / RGB{ids[n]}',fill='white');panels.append(im)
        sheet=Image.new('RGB',(a.width*3,a.height))
        for n,im in enumerate(panels):sheet.paste(im,(n*a.width,0))
        sheet.save(a.output/'attention_contact_sheet.jpg',quality=92)
        receipt.update(status='ISOLATED_EASI_ATTENTION_MASK_COMPLETE',rgb_ids=ids,input_hw=[a.height,a.width],
            pairs=pair_stats,precision='BF16 forward / FP32 heads and attention aggregation',forward_seconds=forward_seconds,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            checkpoint_sha256=json.loads((ROOT/'experiments/TASK009/intake/easi_weight_receipt.json').read_text())['sha256'],
            upstream_base_sha256=hashlib.sha256((SOURCE/'dust3r/cloud_opt/base_opt.py').read_bytes()).hexdigest(),
            threshold=threshold,dynamic_fractions=[float(x.float().mean()) for x in masks],
            score_semantics='Minmax normalized attention score, not calibrated dynamic probability',
            functions_from_unchanged_external_ast=['NoGradParamDict','aggregate_attention_maps','cluster_attention_maps','adaptive_multiotsu_variance'],
            roi_or_detection_accuracy_claim=False,gpu=torch.cuda.get_device_name(),torch=torch.__version__)
    except BaseException as error:
        receipt.update(status='FAILED',error=str(error),traceback=traceback.format_exc());raise
    finally:
        (a.output/'statistics.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
