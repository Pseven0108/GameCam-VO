"""Independent relative-depth consistency and conservative prior candidate.

Metric3D prediction is the alignment anchor, NEVER ground truth. One scale for
the whole short window; no per-frame GT fit, confidence calibration or unit claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',required=True);a=parser.parse_args()
    ds=next(d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()) if d['name']==a.dataset)
    if ds.get('inference_only'):raise ValueError('No admitted K/Metric3D cache; no fabricated depth scale')
    source=Path(ds.get('prior_cache',TASK/'outputs/priors'/a.dataset))
    model=TASK/'outputs/pi3mos'/a.dataset
    report=TASK/'05_fusion_methods/depth_prior'/a.dataset;report.mkdir(parents=True,exist_ok=False)
    frames=[];ratios=[];per_frame=[]
    for fid in ds['rgb_ids']:
        metric=np.load(source/f'depth_{fid:05d}.npy',allow_pickle=False)
        with np.load(model/f'{fid:05d}.npz',allow_pickle=False) as z:
            depth=cv2.resize(z['depth'],metric.shape[::-1],interpolation=cv2.INTER_LINEAR)
            motion=cv2.resize(z['probability'],metric.shape[::-1],interpolation=cv2.INTER_LINEAR)
            conf=z['confidence'].copy()
        valid=np.isfinite(depth)&(depth>0)&np.isfinite(metric)&(metric>0)&(motion<.4)
        if valid.sum()<1024:raise RuntimeError('Insufficient finite static-support depth; not admitted')
        ratio=metric[valid]/depth[valid]
        ratios.append(ratio);per_frame.append(float(np.median(ratio)));frames.append((fid,metric,depth,valid,conf))
    scale=float(np.median(np.concatenate(ratios)))
    instability=float(np.quantile(per_frame,.95)/np.quantile(per_frame,.05))
    # Predeclared gate, without any trajectory score: >2x temporal scale variation is not admitted.
    admitted=np.isfinite(scale) and scale>0 and instability<=2.
    result={'dataset':a.dataset,'scale_to_Metric3D_prediction_units':scale,'per_frame_alignment_scales':per_frame,
        'scale_p95_over_p05':instability,'admitted_as_experimental_VO_prior':bool(admitted),
        'depth_GT_accuracy_established':False,'physical_metric_scale_established':False,
        'confidence_calibration_established':False,'one_scale_per_window':True,
        'offline_uses_full_window':True,'blend_inverse_depth_fraction':.25,'frames':[]}
    out=TASK/'outputs/priors_blend'/a.dataset
    if admitted:out.mkdir(parents=True,exist_ok=False)
    original=json.loads((source/'receipt.json').read_text());receipt=dict(original)
    receipt['depth']=[];receipt['depth_candidate']=result
    for fid,metric,depth,valid,conf in frames:
        aligned=depth*scale
        relative=np.abs(aligned[valid]-metric[valid])/np.maximum(metric[valid],1e-8)
        eligible=valid&(aligned/np.maximum(metric,1e-8)>=.5)&(aligned/np.maximum(metric,1e-8)<=2.)
        result['frames'].append({'rgb_id':fid,'static_valid_fraction':float(valid.mean()),
            'prediction_agreement_relative_median':float(np.median(relative)),
            'prediction_agreement_relative_p90':float(np.quantile(relative,.9)),
            'eligible_fraction':float(eligible.mean()),'confidence_min':float(conf.min()),'confidence_max':float(conf.max()),
            'confidence_used_as_probability':False})
        if admitted:
            blend=metric.copy()
            blend[eligible]=1./(.75/metric[eligible]+.25/aligned[eligible])
            if not np.isfinite(blend).all() or (blend<0).any():raise RuntimeError('Depth candidate nonfinite')
            path=out/f'depth_{fid:05d}.npy';np.save(path,blend)
            receipt['depth'].append({'rgb_id':fid,'sha256':sha(path)})
            shutil.copyfile(source/f'feature_{fid:05d}.npy',out/f'feature_{fid:05d}.npy')
    (report/'INDEPENDENT_DEPTH_ADMISSION.json').write_text(json.dumps(result,indent=2))
    if admitted:
        receipt['status']='COMPLETE';receipt['source_prior_receipt_sha256']=sha(source/'receipt.json')
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='frames'},indent=2))


if __name__=='__main__':main()
