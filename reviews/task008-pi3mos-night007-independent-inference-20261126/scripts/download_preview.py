"""Transfer only already cached RGB preview frames using pinned SSH and hashes."""
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image,ImageDraw
from remote_transport import ROOT,PROJECT,SSH,PORT,ENDPOINT,options

SOURCE='/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487'
MANIFEST=PROJECT/'experiments/VIPER_MATCHED_DUAL_BASELINE_R2/manifests/val_007_full_00001-00487.json'
rows={x['rgb_id']:x for x in json.loads(MANIFEST.read_text('utf-8'))['frames']}
out=ROOT/'outputs/night007/raw_rgb_preview';out.mkdir(parents=True,exist_ok=True)
ids=[281,301,309,312,320,328,332]
for fid in ids:
    p=out/rows[fid]['file'];expected=rows[fid]
    if p.exists():
        assert hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256'];continue
    args=[str(SSH),'-T','-p',PORT,*options(),'root@'+ENDPOINT,'exec /bin/cat -- '+SOURCE+'/'+expected['file']]
    with p.open('xb') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.PIPE,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode==0 and p.stat().st_size==expected['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256']
    with Image.open(p) as im:im.verify()
sheet=Image.new('RGB',(1440,4*438),'#15191f');draw=ImageDraw.Draw(sheet)
for i,fid in enumerate(ids):
    with Image.open(out/rows[fid]['file']) as im:
        assert im.size==(1920,1080)
        sheet.paste(im.convert('RGB').resize((720,405),Image.Resampling.LANCZOS),(i%2*720,i//2*438+28))
    draw.text((i%2*720+8,i//2*438+8),'Night val007 | original RGB '+str(fid).zfill(5)+' | RGB-only selection',fill='white')
p=ROOT/'outputs/night007/contact_sheets/RGB_ONLY_PREVIEW.jpg';p.parent.mkdir(parents=True,exist_ok=True);sheet.save(p,quality=92)
print(json.dumps({'verified_frames':len(ids),'contact_sheet':str(p),'models_used':False},indent=2))
