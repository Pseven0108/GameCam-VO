"""Independent CPU audit of all saved arrays, coordinate restoration and masks."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

R=Path(__file__).resolve().parents[1];src=R/'retrieved';out=R/'analysis';out.mkdir(exist_ok=False)
state=json.loads((src/'INFERENCE_STATE.json').read_text());assert state['model_forwards_complete']==64
manifest=json.loads((src/'INFERENCE_INPUT_OUTPUT_MANIFEST.json').read_text())['records']
stats={(r['mode'],r['target_rgb_id']):r for r in json.loads((src/'INFERENCE_STATISTICS.json').read_text())['frames']}
ident={r['rgb_id']:r for r in json.loads((src/'INPUT_IDENTITY_BEFORE.json').read_text())['frames']}

def independent_bilinear(a,height=1080,width=1920):
    # Float64 half-pixel formula, independently implemented from Torch interpolation.
    y=(np.arange(height,dtype=np.float64)+.5)*(a.shape[0]/height)-.5
    x=(np.arange(width,dtype=np.float64)+.5)*(a.shape[1]/width)-.5
    y=np.maximum(y,0);x=np.maximum(x,0)
    y0=np.floor(y).astype(int);x0=np.floor(x).astype(int)
    y1=np.minimum(y0+1,a.shape[0]-1);x1=np.minimum(x0+1,a.shape[1]-1)
    wy=y-y0;wx=x-x0
    return ((1-wy)[:,None]*((1-wx)[None,:]*a[y0[:,None],x0[None,:]]+wx[None,:]*a[y0[:,None],x1[None,:]])+
            wy[:,None]*((1-wx)[None,:]*a[y1[:,None],x0[None,:]]+wx[None,:]*a[y1[:,None],x1[None,:]]))

rows=[];flat=[]
for record in manifest:
    mode,fid=record['mode'],record['target_rgb_id'];offsets=[-10,-5,0] if mode=='A' else [-20,-15,-10,-5,0]
    assert record['input_ids']==[fid+v for v in offsets]
    for r in record['inputs']:assert r==ident[r['rgb_id']]
    prediction=src/'outputs/night007'/mode/'predictions'/f'{fid:05d}.npz'
    assert prediction.stat().st_size==record['bytes'] and hashlib.sha256(prediction.read_bytes()).hexdigest()==record['sha256']
    with np.load(prediction,allow_pickle=False) as z:
        p=z['dynamic_probability_model'];original=z['dynamic_probability_original'];conf=z['confidence_model'];depth=z['depth_model']
        points=z['local_points_last'];pose=z['camera_pose_last']
        assert p.shape==conf.shape==depth.shape==(378,672) and original.shape==(1080,1920)
        assert points.shape==(378,672,3) and pose.shape==(4,4)
        assert all(a.dtype==np.float32 and np.isfinite(a).all() for a in [p,original,conf,depth,points,pose])
        assert 0<=p.min()<=p.max()<=1 and 0<=conf.min()<=conf.max()<=1 and depth.min()>0
        assert np.array_equal(points[:,:,2],depth)
        assert z['target_rgb_id']==fid and z['context_rgb_ids'].tolist()==record['input_ids']
        reference=independent_bilinear(p);difference=np.abs(reference-original)
        maxdiff=float(difference.max());assert maxdiff<5e-5,'Pixel-grid restoration differs beyond float32 roundoff contract'
        mask=np.asarray(Image.open(src/'outputs/night007'/mode/'masks'/f'{fid:05d}.png'))
        assert np.array_equal(mask,(original>.4).astype(np.uint8)*255)
        original_rgb=src/'outputs/night007/original_rgb'/f'{fid:05d}.jpg'
        assert hashlib.sha256(original_rgb.read_bytes()).hexdigest()==ident[fid]['sha256']
        s=stats[mode,fid]
        for t in [.2,.4,.6]:assert abs(float((original>t).mean())-s['dynamic_original_area'][str(t)])<1e-12
        assert abs(float(conf.mean())-s['confidence_mean'])<1e-12
        rows.append({'mode':mode,'rgb_id':fid,'independent_restoration_max_abs':maxdiff,
                     'independent_restoration_mean_abs':float(difference.mean()),'mask_pixels_above04':int((mask>0).sum()),
                     'raw_probability_min':float(p.min()),'raw_probability_max':float(p.max()),
                     'original_RGB_identity':'PASS','array_and_context_contract':'PASS','mask_exactly_matches_saved_probability':'PASS'})
        flat.append({'mode':mode,'rgb_id':fid,'context_rgb_ids':','.join(map(str,record['input_ids'])),
                     'dynamic_area_02':s['dynamic_original_area']['0.2'],'dynamic_area_04':s['dynamic_original_area']['0.4'],
                     'dynamic_area_06':s['dynamic_original_area']['0.6'],'confidence_mean':s['confidence_mean'],
                     'confidence_P10':s['confidence_quantiles'][1],'confidence_P50':s['confidence_quantiles'][2],
                     'confidence_P90':s['confidence_quantiles'][3],'confidence_P95':s['confidence_quantiles'][4],
                     'GPU_forward_ms':s['forward_GPU_ms'],'end_to_end_seconds':s['per_target_wall_with_saving_seconds'],
                     'peak_allocated_GiB':s['GPU_peak_allocated_bytes']/1024**3,'raw_prediction_sha256':record['sha256']})

assert len(rows)==64 and {(r['mode'],r['rgb_id']) for r in rows}=={(m,f) for m in ['A','B'] for f in range(301,333)}
regions=list(csv.DictReader((src/'RGB_ONLY_REGION_PROBES.csv').open()))
region_summary=[]
for key in sorted({(r['mode'],r['region']) for r in regions}):
    rr=[r for r in regions if (r['mode'],r['region'])==key]
    region_summary.append({'mode':key[0],'region':key[1],'frames':len(rr),'mean_probability':float(np.mean([float(r['mean_probability']) for r in rr])),
                           'max_mean_probability':max(float(r['mean_probability']) for r in rr),'max_area_p04':max(float(r['area_p04']) for r in rr),
                           'not_GT':True})
extra=[]
for mode in ['A','B']:
    rr=[stats[mode,f] for f in range(301,333)];frows=[r for r in flat if r['mode']==mode]
    nonempty=[r['rgb_id'] for r in rows if r['mode']==mode and r['mask_pixels_above04']>0]
    extra.append({'mode':mode,'mean_end_to_end_seconds':float(np.mean([r['end_to_end_seconds'] for r in frows])),
        'mean_confidence':float(np.mean([r['confidence_mean'] for r in rr])),
        'mean_area_thresholds':{str(t):float(np.mean([r['dynamic_original_area'][str(t)] for r in rr])) for t in [.2,.4,.6]},
        'nonempty_mask_RGB_IDs':nonempty,'empty_mask_RGB_IDs':[f for f in range(301,333) if f not in nonempty],
        'Eulerian_IoU_pairs_with_nonzero_union':sum(r['Eulerian_temporal_mask_IoU'] is not None for r in rr),
        'empty_empty_pairs_excluded_from_IoU':sum(r['Eulerian_temporal_mask_IoU'] is None for r in rr[1:]),
        'mean_forward_wall_seconds':float(np.mean([r['forward_wall_seconds'] for r in rr]))})
for name,data in [('SAVED_PREDICTION_AUDIT.csv',rows),('PER_FRAME_STATISTICS.csv',flat),('REGION_SUMMARY.csv',region_summary)]:
    with (out/name).open('x',encoding='utf-8',newline='') as f:writer=csv.DictWriter(f,list(data[0]));writer.writeheader();writer.writerows(data)
result={'status':'ALL64_ARTIFACT_CONTRACTS_PASS','model_runs_during_this_audit':0,'GPU_or_Torch_imported':False,
    'prediction_records':len(rows),'independent_float64_vs_saved_float32_restoration_max_abs':max(r['independent_restoration_max_abs'] for r in rows),
    'restoration_absolute_roundoff_tolerance':5e-5,'mask_vs_saved_probability_exact':True,
    'GT_detection_accuracy_validated':False,'additional_mode_statistics':extra,'region_summary':region_summary,
    'interpretation':'Artifact/coordinate/identity tests; not scientific accuracy or temporal tracking validation'}
with (out/'CPU_ARTIFACT_VALIDATION.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))
