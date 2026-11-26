import hashlib
import json
from pathlib import Path
import gdown

ROOT=Path(__file__).resolve().parents[3]
manifest=json.loads((ROOT/'experiments/TASK009/intake/leap_checkpoint_resolution.json').read_text())
assert manifest['status']=='RESOLVED' and len(manifest['checkpoint'])==1
target=ROOT/'external/weights/leap_kernel.pth'
if target.exists():raise RuntimeError('Preserve existing checkpoint; no overwrite')
result=gdown.download(id=manifest['checkpoint'][0]['id'],output=str(target),quiet=False,timeout=(10,40))
if not result:raise RuntimeError('Official checkpoint download failed')
h=hashlib.sha256()
with target.open('rb') as f:
    for b in iter(lambda:f.read(1048576),b''):h.update(b)
receipt={'public_official_file_id':manifest['checkpoint'][0]['id'],'bytes':target.stat().st_size,'sha256':h.hexdigest()}
(ROOT/'experiments/TASK009/intake/leap_weight_receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
