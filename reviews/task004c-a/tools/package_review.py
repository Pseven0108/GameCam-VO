import pathlib,json,zipfile,hashlib,csv,io,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];ART=ROOT/'artifacts';ART.mkdir(exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
raw=ART/'TASK004C_FIXED_STATE_RAW_EVIDENCE.zip';status=json.loads((ROOT/'evidence/RAW_ARCHIVE_STATUS.json').read_text());local=json.loads((ROOT/'evidence/LOCAL_RAW_ARCHIVE_VERIFICATION.json').read_text());assert local['status']=='PASS' and raw.stat().st_size==status['archive_bytes']
# Retrieve exact policy bytes from the sealed raw archive; no source data extraction.
with zipfile.ZipFile(raw) as z:
 for arm in ['E0','E1']:(ROOT/'policies'/f'{arm}.json').write_bytes(z.read(f'policies/{arm}.json'))
source={}
for q in ROOT.rglob('*'):
 if not q.is_file() or q.is_symlink():continue
 rel=q.relative_to(ROOT)
 if any(p in rel.parts for p in ['artifacts','__pycache__']):continue
 if q.suffix in ['.pyc','.partial']:continue
 if rel.parts[0]=='reports':name=rel.name
 else:name=rel.as_posix()
 assert name not in source;source[name]=q
# Copies embedded as digest-checked small evidence; no model weights/large RGB.
light={n:p for n,p in source.items() if (p.suffix in ['.md','.csv','.json','.png','.pdf','.npy','.diff'] and not any(t in n for t in ['.stdout.txt','.ssh.stderr.txt']) and p.stat().st_size<1024**2)}
for n,p in source.items():
 if n.startswith(('tools/','source/','evaluation_helpers/')) and p.suffix in ['.py','.cu','.cpp','.yaml']:light[n]=p
# Detailed stdout/stderr required by reviewer, selected CPU logs and exact run receipts.
for n,p in source.items():
 if n.startswith(('test_logs/','native_small/','captures/')) and p.stat().st_size<128*1024:light[n]=p
# Avoid duplicated report PDF/PNGs in results if report-root copy already included.
for name in list(light):
 if name.startswith('results/TASK004C_FIXED_STATE_COMPARISON.'):light.pop(name)

def package(name,files):
 p=ART/name;assert not p.exists();manifest={n:{'bytes':q.stat().st_size,'sha256':sha(q)} for n,q in sorted(files.items())}
 text=json.dumps({'files':manifest,'manifest_self_exclusion':'FILE_SHA256_MANIFEST.json and SHA256_MANIFEST.csv are verified by ZIP CRC and independent outer SHA-256, not recursively included in own hash list'},ensure_ascii=False,indent=2)
 buff=io.StringIO(newline='');w=csv.writer(buff);w.writerow(['path','bytes','sha256']);w.writerows((n,m['bytes'],m['sha256']) for n,m in manifest.items())
 with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for n,q in sorted(files.items()):z.write(q,n)
  z.writestr('FILE_SHA256_MANIFEST.json',text);z.writestr('SHA256_MANIFEST.csv',buff.getvalue())
 count=0
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  for n,m in manifest.items():b=z.read(n);assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'];count+=1
 return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),crc_members_passed=len(manifest)+2,internal_sha256_passed=count,exit_code=0)
full=package('GAMECAM_TASK004C_MECHANISM_ISOLATION_REVIEW.zip',source)
small=package('GAMECAM_TASK004C_REVIEW_LIGHT_FOR_GPT.zip',light)
result=dict(status='PASS',raw_archive=local,full_review=full,light_review=small,all_archives_crc_and_internal_sha256_passed=True,original_remote_data_deleted=False)
(ART/'ARTIFACT_VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf8')
with (ART/'ARTIFACT_SHA256.csv').open('w',newline='',encoding='utf8') as f:
 w=csv.writer(f);w.writerow(['file','bytes','sha256']);w.writerow([raw.name,status['archive_bytes'],status['archive_sha256']]);w.writerows([pathlib.Path(x['path']).name,x['bytes'],x['sha256']] for x in [full,small])
print(json.dumps(result,indent=2))
