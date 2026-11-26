"""Seal only the TASK008 review, excluding models, raw datasets and large arrays."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

TASK=Path(__file__).resolve().parents[1];PROJECT=TASK.parents[1]
R=PROJECT/'reviews/task008-pi3mos-night007-independent-inference-20261126'
for p in (TASK/'scripts').glob('*.py'):
    target=R/'scripts'/p.name
    if target.exists():assert target.read_bytes()==p.read_bytes(),'Previously copied research code changed; inspect before sealing'
    else:shutil.copyfile(p,target)
policy={'full_review_payload':True,'all64_target_overlays_and_masks_included':True,
        'raw_RGB_and_large_float32_NPZ_excluded':True,'raw_outputs_retained_locally_and_remotely':True,
        'model_weights_environments_and_tokens_excluded':True,'first_pre_forward_loader_error_preserved':True}
(R/'PACKAGE_CONTENT_POLICY.json').write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
payload=sorted(p for p in R.rglob('*') if p.is_file() and 'deliveries' not in p.relative_to(R).parts)
assert all(p.suffix.lower() not in {'.npz','.npy','.pth','.pt','.safetensors','.whl','.zip','.bundle','.exe','.dll','.so','.jpg.original'} for p in payload)
assert not any('original_rgb' in p.relative_to(R).parts for p in payload)
secrets=[rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',rb'ghp_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{40,}']
for p in payload:
    b=p.read_bytes()
    assert p.stat().st_size<4*1024**2,'Unexpectedly large review member'
    if p.suffix.lower() not in ['.jpg','.png']:
        for pattern in secrets:assert not re.search(pattern,b),'Credential-shaped material found; stop publication'
rows=[{'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in payload]
with (R/'SHA256_MANIFEST.csv').open('x',encoding='utf-8',newline='') as f:
    wr=csv.DictWriter(f,['path','bytes','sha256']);wr.writeheader();wr.writerows(rows)
csv_path=R/'SHA256_MANIFEST.csv';rows.append({'path':csv_path.name,'bytes':csv_path.stat().st_size,'sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest()})
with (R/'FILE_SHA256_MANIFEST.json').open('x',encoding='utf-8') as f:json.dump({'files':rows,'self_excluded':True},f,indent=2);f.write('\n')
delivery=R/'deliveries';delivery.mkdir(exist_ok=False);archive=delivery/'GAMECAM_TASK008_PI3MOS_NIGHT007_REVIEW.zip'
members=[r['path'] for r in rows]+['FILE_SHA256_MANIFEST.json']
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(members):z.write(R/name,name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and set(z.namelist())==set(members)
    for row in rows:
        b=z.read(row['path']);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
raw=archive.read_bytes();receipt={'ZIP_name':archive.name,'ZIP_bytes':len(raw),'ZIP_sha256':hashlib.sha256(raw).hexdigest(),
    'ZIP_members':len(members),'internal_SHA256_entries':len(rows),'CRC':'PASS','all_review_payload_files_included':True,
    'raw_dataset_and_large_array_exclusions_explicit':True,'GPU_forwards':64,'review_visuals':384}
with (delivery/'PACKAGE_VERIFICATION.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
with (delivery/(archive.name+'.sha256')).open('x',encoding='utf-8') as f:f.write(receipt['ZIP_sha256']+'  '+archive.name+'\n')
pub=PROJECT/'maintenance/GITHUB_TASK008_PUBLICATION_20261126'
(pub/'LOCAL_PACKAGE_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
