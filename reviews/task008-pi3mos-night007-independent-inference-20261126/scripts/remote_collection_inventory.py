"""Inventory only this experiment's outputs; exclude environments and model assets."""
import hashlib
import json
from pathlib import Path

w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
assert (w/'ORIGINAL_ASSET_PRESERVATION.json').is_file()
rows=[]
for p in sorted(w.rglob('*')):
    if not p.is_file() or p.is_symlink():continue
    rel=p.relative_to(w)
    if rel.parts[0] in ['wheelhouse','tmp','hub_cache','torch_cache']:continue
    if rel.parts[0] not in ['scripts','configs','logs','outputs','preprocess_contract_fixture'] and p.suffix not in ['.json','.txt','.csv','.py']:continue
    if p.name=='RESULT_COLLECTION_MANIFEST.json':continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    rows.append({'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
data={'files':rows,'bytes':sum(r['bytes'] for r in rows),'model_weights_or_environment_binaries_included':False,
      'purpose':'Private local evidence recovery; original RGB excluded from public review later'}
with (w/'RESULT_COLLECTION_MANIFEST.json').open('x') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps({'files':len(rows),'bytes':data['bytes'],'model_binaries':False}))
