"""Package the evidence and all added source; exclude private transport dumps."""
import csv,hashlib,json,pathlib,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from verify_review import verify
selected=set()
def add(path):
    path=pathlib.Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    selected.add(path)
for p in ROOT.iterdir():
    if p.is_file() and p.suffix in ('.md','.json','.csv'):add(p)
for name in ('native_control','checkpoint','schedule','runner','configs','tests','tools'):
    for p in (ROOT/name).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.yaml'):add(p)
changed=json.loads((ROOT/'evidence/PATCHED_FILES.json').read_text())
references=['src/geom/ba.py','src/modules/droid_net/corr.py','task003_observer.py','task004_controls.py','.official_archive.json']
for name in set(changed+references):
    add(ROOT/'source_before'/name);add(ROOT/'source_candidate'/name)
add(ROOT/'artifacts/NATIVE_CONTROL_INTERFACE.patch')
safe=['USER_AUTHORIZATION.txt','PHASE0_REVIEW_SAFE.json','PHASE0_receipt.json','LOCAL_BASELINE_MANIFEST.json',
      'PATCHED_FILES.json','ALGORITHM_PRESERVATION.json','FINAL_GIT_IDENTITIES.json','EVIDENCE_INDEX.json',
      'FINAL_PROTECTION.json','FINAL_PROTECTION_handoff.json','CPU_NATIVE_RELEASE.json','CPU_NATIVE_RELEASE_handoff.json',
      'GPU_ADMISSION_FINAL.json','GPU_ADMISSION_handoff.json','FINAL_REMOTE_PROTECTION_receipt.json','FINAL_REMOTE_PROTECTION_handoff_receipt.json']
for name in safe:add(ROOT/'evidence'/name)
for p in (ROOT/'evidence').glob('CPU_*_RECEIPT.json'):add(p)
for p in (ROOT/'evidence').glob('DEPLOY_CPU_*_receipt.json'):add(p)
for p in (ROOT/'evidence/CPU_handoff').rglob('*'):
    if p.is_file() and p.suffix!='.zip':add(p)
demo=ROOT/'evidence/CPU_DEMONSTRATION_handoff/artifacts'
for p in demo.rglob('*'):
    if p.is_file():add(p)
# Preserve the documented official-vs-historical execution difference.
reference=ROOT/'evidence/HISTORICAL_EXECUTION_VS_OFFICIAL.patch'
with reference.open('xb') as out:out.write((ROOT.parent/'DROID_W_TASK004C_B_MINIMAL_CONTROL_20261123T183335782Z/source_reference/HISTORICAL_EXECUTION_VS_OFFICIAL.patch').read_bytes())
add(reference)
for p in selected:
    # These raw process command lines were kept private; never ship access tokens.
    if p.name in ('PHASE0.json','PHASE0.stdout.txt'):raise ValueError('Private Phase0 transport file selected')
rows=[]
for p in sorted(selected):
    raw=p.read_bytes();rows.append({'file':p.relative_to(ROOT).as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
csv_path=ROOT/'SHA256_MANIFEST.csv'
with csv_path.open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['file','bytes','sha256']);w.writeheader();w.writerows(rows)
add(csv_path);raw=csv_path.read_bytes();rows.append({'file':csv_path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
manifest={'schema':'GAMECAM_REVIEW_FILE_SHA256_V1','manifest_self_excluded':True,
          'files':{r['file']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in sorted(rows,key=lambda r:r['file'])}}
mpath=ROOT/'FILE_SHA256_MANIFEST.json'
with mpath.open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
add(mpath)
output=ROOT/'artifacts/TASK004C_B_NATIVE_INTEGRATION_FINAL_REVIEW.zip'
with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(selected):z.write(p,p.relative_to(ROOT).as_posix())
result=verify(output)
with (ROOT/'artifacts/PACKAGE_INTEGRITY.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
with (ROOT/'artifacts/TASK004C_B_NATIVE_INTEGRATION_FINAL_REVIEW.zip.sha256').open('x') as f:f.write(result['ZIP_sha256']+'  '+output.name+'\n')
print(json.dumps(result,indent=2))
