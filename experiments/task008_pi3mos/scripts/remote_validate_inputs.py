"""Read-only input hashes and baseline protection snapshot; no model import."""
import hashlib
import json
from pathlib import Path

W=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
RGB=Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487')
MP=Path('/root/rivermind-data/VIPER_MATCHED_DUAL_BASELINE_R2/manifests/val_007_full_00001-00487.json')
rows={r['rgb_id']:r for r in json.loads(MP.read_text())['frames']}
files=[]
for f in range(281,333):
    p=RGB/rows[f]['file'];b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
    assert len(b)==rows[f]['bytes'] and h==rows[f]['sha256'],'Original RGB input identity mismatch'
    files.append({'rgb_id':f,'path':str(p),'bytes':len(b),'sha256':h})
source=Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/source/DROID-W')
protected=[]
for p in sorted(source.rglob('*')):
    if p.is_file() and p.suffix.lower() in {'.py','.yaml','.yml','.cpp','.cu','.h','.json'}:
        b=p.read_bytes();protected.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
for name,data in [('INPUT_IDENTITY_BEFORE.json',{'frames':files,'manifest_path':str(MP),'manifest_sha256':hashlib.sha256(MP.read_bytes()).hexdigest(),
                  'target_ids':list(range(301,333)),'context_only_ids':list(range(281,301)),'identity_verified':True}),
                  ('BASELINE_PROTECTION_BEFORE.json',{'files':protected,'scope':'Existing Task003 DROID-W source/config and observer JSON, no model binaries loaded'})]:
    with (W/name).open('x',encoding='utf-8') as out:json.dump(data,out,indent=2);out.write('\n')
print(json.dumps({'RGB_hashes_verified':len(files),'target_count':32,'source_files_protected':len(protected),
                  'source_RGB_unmodified':True,'models_loaded':0},indent=2))
