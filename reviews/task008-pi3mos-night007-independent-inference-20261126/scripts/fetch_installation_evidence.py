"""Recover small task-owned deployment/first-load records, never credentials or wheels."""
import base64
import hashlib
import json
from remote_transport import ROOT,run

script='''import base64,hashlib,json,pathlib
w=pathlib.Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1');rows=[]
names=[p.name for p in w.iterdir() if p.is_file() and p.suffix in ['.json','.txt']]
names += ['logs/'+p.name for p in (w/'logs').iterdir() if p.is_file() and p.suffix in ['.txt','.log']]
for name in sorted(names):
 p=w/name
 assert p.stat().st_size<2*1024**2
 b=p.read_bytes();rows.append({'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
                             'base64':base64.b64encode(b).decode()})
print(json.dumps(rows))
'''
rows=json.loads(run(script,'INSTALLATION_EVIDENCE_READBACK',timeout=90))
dest=ROOT/'installation_evidence';dest.mkdir(exist_ok=False)
for row in rows:
    b=base64.b64decode(row['base64']);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
    p=dest/row['path'];p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
print(json.dumps({'small_installation_records':len(rows),'total_bytes':sum(r['bytes'] for r in rows),
                  'initial_GPU_forwards':0,'binary_weights_or_credentials_transferred':False}))
