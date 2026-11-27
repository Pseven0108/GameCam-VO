"""Evidence figures from actual predictions; neither overlays nor areas are accuracy."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
ds=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
dest=TASK/'08_reports/figures';dest.mkdir(parents=True,exist_ok=True)
summaries=[]
for d in ds:
    models=[m for m in ['pi3mos','gmos','geomotion','geomotion_full'] if (TASK/'outputs'/m/d['name']/'receipt.json').exists() and
        json.loads((TASK/'outputs'/m/d['name']/'receipt.json').read_text()).get('status')=='COMPLETE']
    if not models:continue
    examples=[d['rgb_ids'][i] for i in [4,16,28]]
    hh,ww=d['hw']  # preserve 4:3 real scenes and 16:9 game scenes in figures
    canvas=Image.new('RGB',((len(models)+1)*ww,len(examples)*(hh+28)),(20,20,20));draw=ImageDraw.Draw(canvas)
    for row,fid in enumerate(examples):
        rgb=np.array(Image.open(Path(d['rgb_dir'])/(f'{fid:05d}'+d.get('image_suffix','.jpg'))).convert('RGB').resize((ww,hh)))
        y=row*(hh+28);canvas.paste(Image.fromarray(rgb),(0,y+28));draw.text((4,y+5),f'{d["name"]} RGB{fid}',fill='white')
        for col,m in enumerate(models,1):
            with np.load(TASK/'outputs'/m/d['name']/f'{fid:05d}.npz',allow_pickle=False) as z:p=z['probability']
            p=cv2.resize(p,(ww,hh),interpolation=cv2.INTER_LINEAR)
            overlay=rgb.astype(np.float32)*(.85-.35*p[...,None])+np.array([255,20,0])[None,None,:]*(.15+.35*p[...,None])
            # Unchanged static pixels: only colour the predicted dynamic support.
            alpha=.65*p[...,None];overlay=rgb*(1-alpha)+np.array([255,20,0])*alpha
            canvas.paste(Image.fromarray(np.uint8(np.clip(overlay,0,255))),(col*ww,y+28))
            draw.text((col*ww+4,y+5),f'{m} | score>.4: {(p>.4).mean():.3%}',fill='white')
    canvas.save(dest/(d['name']+'_overlays.jpg'),quality=90)
    for m in models:
        rows=[]
        for fid in d['rgb_ids']:
            path=TASK/'outputs'/m/d['name']/f'{fid:05d}.npz'
            if not path.exists():continue
            with np.load(path,allow_pickle=False) as z:p=z['probability']
            rows.append({'rgb_id':fid,'mean':float(p.mean()),'area_gt04':float((p>.4).mean()),'area_gt05':float((p>.5).mean()),
                         'p99':float(np.quantile(p,.99))})
        summaries.append({'dataset':d['name'],'domain':d['domain'],'model':m,'frames':rows,
                          'accuracy_GT_available':False})
(TASK/'03_candidate_inference/MODEL_SCORE_DISTRIBUTIONS.json').write_text(json.dumps(summaries,indent=2))
print('Rendered',len(list(dest.glob('*overlays.jpg'))),'actual-model contact sheets')
