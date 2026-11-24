import pathlib,json,hashlib,zipfile,time,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];p=ROOT/'artifacts/TASK004C_FIXED_STATE_RAW_EVIDENCE.zip';receipt=json.loads((ROOT/'evidence/RAW_ARCHIVE_STATUS.json').read_text(encoding='utf8'));start=time.monotonic();crc=sha=0
h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
assert p.stat().st_size==receipt['archive_bytes'] and h.hexdigest()==receipt['archive_sha256']
with zipfile.ZipFile(p) as z:
 manifest=json.loads(z.read('RAW_SHA256_MANIFEST.json'))['files'];names=z.namelist();assert len(set(names))==len(names) and len(names)==len(manifest)+1
 for info in z.infolist():
  name=info.filename;assert not name.startswith('/') and '..' not in pathlib.PurePosixPath(name).parts
  hh=hashlib.sha256();n=0
  with z.open(info) as f:
   for b in iter(lambda:f.read(8*1024**2),b''):hh.update(b);n+=len(b)
  crc+=1
  if name in manifest:
   assert n==manifest[name]['bytes'] and hh.hexdigest()==manifest[name]['sha256'];sha+=1
 result=dict(status='PASS',exit_code=0,archive=str(p),archive_bytes=p.stat().st_size,archive_sha256=h.hexdigest(),crc_members_passed=crc,internal_sha256_passed=sha,elapsed_seconds=time.monotonic()-start,extract_all=False,model_weights_included=False,GT_sources_included=False)
(ROOT/'evidence/LOCAL_RAW_ARCHIVE_VERIFICATION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
