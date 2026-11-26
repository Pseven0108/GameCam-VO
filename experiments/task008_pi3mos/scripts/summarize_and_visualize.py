"""CPU A/B proxy summaries and complete contact sheets, without GT claims."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw

p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--roi-plan',required=True);args=p.parse_args()
c=json.loads(Path(args.config).read_text());w=Path(c['remote_output']);out=w/'outputs/night007';cs=out/'contact_sheets';cs.mkdir()
stats=json.loads((w/'INFERENCE_STATISTICS.json').read_text())['frames'];roi=json.loads(Path(args.roi_plan).read_text())
by={(x['mode'],x['target_rgb_id']):x for x in stats};targets=list(range(301,333))
summaries=[];pair=[];regions=[]
for mode in ['A','B']:
    rows=[by[mode,f] for f in targets]
    summaries.append({'mode':mode,'context_frames':3 if mode=='A' else 5,'predictions':len(rows),
        'mean_forward_GPU_ms':float(np.mean([r['forward_GPU_ms'] for r in rows])),
        'median_forward_GPU_ms':float(np.median([r['forward_GPU_ms'] for r in rows])),
        'mean_forward_GPU_ms_excluding_first':float(np.mean([r['forward_GPU_ms'] for r in rows[1:]])),
        'maximum_peak_allocated_GiB':max(r['GPU_peak_allocated_bytes'] for r in rows)/1024**3,
        'maximum_peak_reserved_GiB':max(r['GPU_peak_reserved_bytes'] for r in rows)/1024**3,
        'mean_dynamic_area_p04':float(np.mean([r['dynamic_original_area']['0.4'] for r in rows])),
        'mean_Eulerian_probability_MAD':float(np.mean([r['Eulerian_temporal_probability_MAD'] for r in rows[1:]])),
        'mean_Eulerian_mask_IoU':float(np.mean([r['Eulerian_temporal_mask_IoU'] for r in rows[1:] if r['Eulerian_temporal_mask_IoU'] is not None])) if any(r['Eulerian_temporal_mask_IoU'] is not None for r in rows[1:]) else None,
        'GT_accuracy':None,'temporal_metric':'Uncompensated same-pixel proxy, not true object consistency or accuracy'})
    sheet=Image.new('RGB',(4*480,8*300),'#11161c');draw=ImageDraw.Draw(sheet)
    for i,fid in enumerate(targets):
        with Image.open(out/mode/'overlays'/f'{fid:05d}.jpg') as im:sheet.paste(im.resize((480,270),Image.Resampling.LANCZOS),(i%4*480,i//4*300+25))
        draw.text((i%4*480+8,i//4*300+6),f'{mode} | RGB {fid:05d} | threshold0.4',fill='white')
    sheet.save(cs/f'{mode}_ALL32_OVERLAYS.jpg',quality=94)
for fid in targets:
    values={}
    for mode in ['A','B']:
        with np.load(out/mode/'predictions'/f'{fid:05d}.npz',allow_pickle=False) as z:prob=z['dynamic_probability_original']
        values[mode]=prob
        h,ww=prob.shape
        for name,box in roi['all_target_fixed_regions_normalized_xyxy'].items():
            x1,y1,x2,y2=box;a=prob[int(y1*h):int(y2*h),int(x1*ww):int(x2*ww)]
            regions.append({'mode':mode,'rgb_id':fid,'region':name,'mean_probability':float(a.mean()),'area_p04':float((a>.4).mean()),'GT_label':False})
        if fid==312:
            x1,y1,x2,y2=roi['frame312_vehicle_box_normalized_xyxy'];a=prob[int(y1*h):int(y2*h),int(x1*ww):int(x2*ww)]
            regions.append({'mode':mode,'rgb_id':fid,'region':'truck_candidate_RGB_only_box','mean_probability':float(a.mean()),'area_p04':float((a>.4).mean()),'GT_label':False})
    a,b=values['A']>.4,values['B']>.4;union=(a|b).sum()
    pair.append({'rgb_id':fid,'A_B_probability_MAD':float(np.abs(values['A']-values['B']).mean()),
                 'A_B_mask_agreement_IoU':float((a&b).sum()/union) if union else None,'GT_accuracy':False})
selected=[301,309,312,320,328,332]
sheet=Image.new('RGB',(1920,len(selected)*394),'#14191f');draw=ImageDraw.Draw(sheet)
for i,fid in enumerate(selected):
    for j,(folder,label) in enumerate([('original_rgb','RGB'),('A/overlays','3-frame A'),('B/overlays','5-frame B')]):
        with Image.open(out/folder/f'{fid:05d}.jpg') as im:sheet.paste(im.resize((640,360),Image.Resampling.LANCZOS),(640*j,394*i+28))
        draw.text((640*j+8,394*i+6),f'{label} | RGB{fid:05d} | red=M>0.4',fill='white')
sheet.save(cs/'A_B_SELECTED_COMPARISON.jpg',quality=95)
detail=Image.new('RGB',(1920,2*394),'#14191f');draw=ImageDraw.Draw(detail)
entries=[('original_rgb/00312.jpg','original RGB312'),('B/probability_heat/00312.jpg','5-frame probability [0,1], blue low / red high'),
         ('B/overlays/00312.jpg','5-frame threshold0.4 overlay'),('B/masks/00312.png','5-frame binary mask, no GT'),
         ('B/confidence/00312.jpg','native confidence [0,1], not DROID U'),('B/depth/00312.jpg','local_points z, display-only nonmetric')]
for i,(name,label) in enumerate(entries):
    with Image.open(out/name) as im:detail.paste(im.convert('RGB').resize((640,360),Image.Resampling.LANCZOS),(i%3*640,i//3*394+28))
    draw.text((i%3*640+7,i//3*394+7),label,fill='white')
detail.save(cs/'RGB312_FIVE_FRAME_DETAIL.jpg',quality=95)
for name,rows in [('MODE_COMPARISON.csv',summaries),('A_B_FRAME_COMPARISON.csv',pair),('RGB_ONLY_REGION_PROBES.csv',regions)]:
    with (w/name).open('x',encoding='utf-8',newline='') as f:wr=csv.DictWriter(f,list(rows[0]));wr.writeheader();wr.writerows(rows)
result={'mode_summary':summaries,'A_B_probability_MAD_mean':float(np.mean([r['A_B_probability_MAD'] for r in pair])),
        'region_plan':roi,'GT_detection_metrics':None,'all32_targets_in_both_modes':True,
        'original_probability_shape':[1080,1920],'model_probability_shape':[378,672],
        'coordinate_correspondence':'Recorded no-crop scaling; restored probabilities and overlays use original RGB grid',
        'limitations':['No pixelwise dynamic GT','Eulerian IoU/MAD confounded by object and camera motion','Parked vehicle/pedestrian/pure-rotation controls absent','Only one32-frame Night007 window'],
        'next_stage_or_DROID_integration_started':False}
with (w/'TASK008_SUMMARY_STATISTICS.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps(result,indent=2))
