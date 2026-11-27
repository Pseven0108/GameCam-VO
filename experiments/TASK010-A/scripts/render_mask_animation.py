"""Short raw-output comparison GIFs, no interpolated masks or generated frames."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
names=['night007_dev','rain030_holdout','downtown1_holdout','wildworld_thirdperson_qual']
for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()):
    if d['name'] not in names:continue
    models=[m for m in ['pi3mos','gmos','geomotion','geomotion_full'] if (TASK/'outputs'/m/d['name']/'receipt.json').exists() and json.loads((TASK/'outputs'/m/d['name']/'receipt.json').read_text()).get('status')=='COMPLETE']
    frames=[];h,w=d['hw']
    for fid in d['rgb_ids']:
        rgb=np.array(Image.open(Path(d['rgb_dir'])/(f'{fid:05d}'+d.get('image_suffix','.jpg'))).convert('RGB').resize((w,h)))
        canvas=Image.new('RGB',((len(models)+1)*w,h+30),(15,15,15));draw=ImageDraw.Draw(canvas)
        canvas.paste(Image.fromarray(rgb),(0,30));draw.text((5,5),f'Original RGB{fid}',fill='white')
        for col,m in enumerate(models,1):
            with np.load(TASK/'outputs'/m/d['name']/f'{fid:05d}.npz',allow_pickle=False) as z:p=cv2.resize(z['probability'],(w,h))
            a=.65*p[...,None];overlay=np.uint8(np.clip(rgb*(1-a)+np.array([255,20,0])*a,0,255))
            canvas.paste(Image.fromarray(overlay),(col*w,30));draw.text((col*w+5,5),m,fill='white')
        frames.append(canvas)
    frames[0].save(TASK/'08_reports/figures'/(d['name']+'_actual_masks.gif'),save_all=True,append_images=frames[1:],duration=130,loop=0,optimize=True)
    print('Animated actual arrays',d['name'],len(frames))
