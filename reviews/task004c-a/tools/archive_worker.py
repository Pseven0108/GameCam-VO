"""Seal all new raw evidence; standard library only; no model or GPU calls."""
import pathlib,sys,os,json,time,zipfile,hashlib,shutil,traceback
r=pathlib.Path(sys.argv[1]);out=r/'archives';report={'phase':'running','started_unix':time.time(),'torch_imported':False};receipt=out/'RAW_ARCHIVE_STATUS.json';receipt.write_text(json.dumps(report,indent=2));archive=out/'TASK004C_FIXED_STATE_RAW_EVIDENCE.zip';floor=10*1024**3;maxzip=4*1024**3
try:
 assert not archive.exists()
 for name in ['E0_D1','E0_D0','E1_D1','E1_D0']:assert json.loads((r/'replays'/name/'STATUS.json').read_text())['exit_code']==0
 for name in ['ANALYSIS_PROCESS.json','COMMON_SUPPORT_PROCESS.json']:assert json.loads((r/'analysis'/name).read_text())['exit_code']==0
 paths=sorted(q for q in r.rglob('*') if q.is_file() and not q.is_symlink() and not any(k in q.parts for k in ['archives','__pycache__']))
 manifest={};uncompressed=0
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
  for q in paths:
   name=q.relative_to(r).as_posix();before=q.stat();h=hashlib.sha256()
   with q.open('rb') as src,z.open(name,'w',force_zip64=True) as dst:
    while True:
     b=src.read(8*1024**2)
     if not b:break
     assert shutil.disk_usage(r).free>=floor+16*1024**2,'STORAGE_FLOOR'
     assert archive.stat().st_size<maxzip,'ARCHIVE_SIZE_CAP'
     h.update(b);dst.write(b)
   after=q.stat();assert before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns,'file changed while sealing'
   manifest[name]={'bytes':after.st_size,'sha256':h.hexdigest()};uncompressed+=after.st_size
  z.writestr('RAW_SHA256_MANIFEST.json',json.dumps({'files':manifest,'self_exclusion':'RAW_SHA256_MANIFEST.json excludes itself; final ZIP has independent outer SHA-256'},ensure_ascii=False,indent=2))
 crc=0;verified=0
 with zipfile.ZipFile(archive) as z:
  assert len(z.infolist())==len(manifest)+1
  for info in z.infolist():
   h=hashlib.sha256();n=0
   with z.open(info) as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);n+=len(b)
   crc+=1
   if info.filename in manifest:assert n==manifest[info.filename]['bytes'] and h.hexdigest()==manifest[info.filename]['sha256'];verified+=1
 h=hashlib.sha256()
 with archive.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 report.update(phase='complete',archive=str(archive),archive_sha256=h.hexdigest(),archive_bytes=archive.stat().st_size,uncompressed_payload_bytes=uncompressed,crc_members_passed=crc,internal_sha256_passed=verified,file_count=len(manifest),exit_code=0,finished_unix=time.time(),disk_free_bytes=shutil.disk_usage(r).free,originals_deleted=False,torch_imported='torch' in sys.modules)
 (out/'RAW_SHA256_MANIFEST.json').write_text(json.dumps({'files':manifest},indent=2))
except Exception as e:
 traceback.print_exc();report.update(phase='failed',exit_code=1,error=repr(e),finished_unix=time.time())
finally:receipt.write_text(json.dumps(report,indent=2));print(json.dumps(report))
sys.exit(report['exit_code'])
