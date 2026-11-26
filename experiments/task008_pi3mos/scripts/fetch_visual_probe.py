"""Fetch a small current-output preview; no extra model calls."""
import base64
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageDraw
from remote_transport import run,ROOT

w='/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED'
names=['outputs/night007/original_rgb/00312.jpg','outputs/night007/A/overlays/00312.jpg',
       'outputs/night007/B/overlays/00312.jpg','outputs/night007/B/probability_heat/00312.jpg']
script='''import base64,hashlib,json,pathlib
w=pathlib.Path(WORK);rows=[]
for name in NAMES:
 b=(w/name).read_bytes();rows.append({'name':name,'sha256':hashlib.sha256(b).hexdigest(),'content':base64.b64encode(b).decode()})
print(json.dumps(rows))
'''.replace('WORK',repr(w)).replace('NAMES',repr(names))
rows=json.loads(run(script,'VISUAL_PROBE_RGB312',timeout=60));dest=ROOT/'outputs/night007/live_visual_probe';dest.mkdir()
sheet=Image.new('RGB',(1280,772),'#14191f');draw=ImageDraw.Draw(sheet)
for i,row in enumerate(rows):
 b=base64.b64decode(row['content']);assert hashlib.sha256(b).hexdigest()==row['sha256']
 p=dest/('RGB312_'+str(i)+'.jpg');p.write_bytes(b)
 with Image.open(p) as im:sheet.paste(im.resize((640,360),Image.Resampling.LANCZOS),(i%2*640,i//2*386+26))
 draw.text((i%2*640+8,i//2*386+6),row['name'].split('night007/')[1],fill='white')
sheet.save(dest/'RGB312_ACTUAL_OUTPUT_PROBE.jpg',quality=95)
print(str(dest/'RGB312_ACTUAL_OUTPUT_PROBE.jpg'))
