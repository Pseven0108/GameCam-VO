"""Create and verify this small protocol-only review package. No research execution."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib, json, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'
OUT.mkdir(exist_ok=True)
MANIFEST=ROOT/'FILE_SHA256_MANIFEST.json'
ZIP=OUT/'GAMECAM_TASK004C_B_PROTOCOL_REVIEW.zip'
if ZIP.exists():
    raise SystemExit('Refusing to overwrite an existing review ZIP')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def included(path):
    rel=path.relative_to(ROOT)
    return path.is_file() and rel.parts[0]!='artifacts' and path!=MANIFEST

paths=sorted((p for p in ROOT.rglob('*') if included(p)),key=lambda p:p.relative_to(ROOT).as_posix())
files=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
manifest={'schema':'GAMECAM_REVIEW_SHA256_MANIFEST_V1','task':'TASK004C-B-PROTOCOL',
    'generated_utc':datetime.now(timezone.utc).isoformat(),'algorithm':'SHA-256',
    'coverage':'All packaged files except this self-manifest; external artifacts/ receipts are outside package',
    'exclusions':['FILE_SHA256_MANIFEST.json','artifacts/**'], 'files':files}
MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')
with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in paths+[MANIFEST]:
        z.write(p,p.relative_to(ROOT).as_posix())

with zipfile.ZipFile(ZIP) as z:
    names=z.namelist()
    if len(names)!=len(set(names)):
        raise AssertionError('duplicate members')
    if any(n.startswith('/') or '..' in n.split('/') or ':' in n.split('/')[0] for n in names):
        raise AssertionError('unsafe member path')
    crc=z.testzip()
    if crc is not None:
        raise AssertionError('CRC failed: '+crc)
    stored=json.loads(z.read('FILE_SHA256_MANIFEST.json'))
    expected={item['path'] for item in stored['files']}|{'FILE_SHA256_MANIFEST.json'}
    if set(names)!=expected:
        raise AssertionError('SHA coverage mismatch')
    for item in stored['files']:
        raw=z.read(item['path'])
        if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise AssertionError('internal SHA or size mismatch: '+item['path'])
    prohibited={'.pth','.pt','.safetensors','.npz','.rrd','.jpg','.jpeg','.mp4'}
    if any(Path(n).suffix.lower() in prohibited for n in names):
        raise AssertionError('Unexpected model/data/runtime payload')
    required=[p for p in ROOT.glob('TASK004C_B_*') if p.is_file()]
    if any(p.name not in names for p in required):
        raise AssertionError('Required protocol file absent')

report={'task':'TASK004C-B-PROTOCOL','utc':datetime.now(timezone.utc).isoformat(),
    'zip_file':ZIP.name,'zip_bytes':ZIP.stat().st_size,'zip_sha256':sha(ZIP),
    'zip_crc':'PASS','member_count':len(names),'internal_SHA256_entries':len(stored['files']),
    'internal_SHA256_matches':len(stored['files']),'SHA_coverage':'ALL_FILES_EXCEPT_SELF_MANIFEST',
    'member_coverage':'EXACT','unsafe_paths':0,'duplicate_members':0,'no_models_RGB_GT_or_runtime_checkpoints':True,
    'delivery_static_checks':json.loads((ROOT/'evidence/DELIVERY_STATIC_VALIDATION.json').read_text(encoding='utf-8'))['passed'],
    'exit_code':0,'runtime_or_GPU_experiments_executed':False}
(OUT/'PACKAGE_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+chr(10),encoding='utf-8')
(OUT/'ZIP_SHA256.txt').write_text(report['zip_sha256']+'  '+ZIP.name+chr(10),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
