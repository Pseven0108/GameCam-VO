"""Lossless storage representation of consumed current R3 logs, after verified local copies."""
import hashlib,json,sys
from remote import ROOT,call
modes=('B4',)
proof={}
for mode in modes:
 from evidence_locations import stage_dir
 p=stage_dir(mode)
 receipt=json.loads((p/'PROCESS_RECEIPT.json').read_text());assert receipt['exit_code']==0 and (p/'SUCCESS.json').is_file()
 for n in ('observer.jsonl','rerun_stream.rrd'):
  q=p/n
  h=hashlib.sha256()
  with q.open('rb') as f:
   for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
  proof[mode+'/'+n]={'bytes':q.stat().st_size,'sha256':h.hexdigest()}
code=r'''
import os,pathlib,gzip,hashlib,json,stat,shutil,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
proof=PROOF
# S0 producer completed; preserve raw schedule for B3. Canonical local evidence verified.
for mode in ('B4',):
 out=r/'attempts'/mode;receipt=json.loads((out/'PROCESS_RECEIPT.json').read_text());assert receipt['exit_code']==0 and (out/'SUCCESS.json').is_file()
report={'scope':'LOSSLESS_COMPRESSION_OF_COMPLETED_CONSUMED_CURRENT_R3_LOGS','local_canonical_raw_copies_verified':True,'historical_assets_touched':False,'model_runs_launched':0,'records':[],'before_free_bytes':shutil.disk_usage(r).free,'unix':time.time()}
for rel,want in proof.items():
 p=r/'attempts'/rel;assert p.resolve()==p and not p.is_symlink()
 z=p.with_name(p.name+'.gz');tmp=p.with_name(p.name+'.gzip-in-progress')
 assert p.is_file() and not z.exists() and not tmp.exists()
 s=p.stat();assert s.st_nlink==1 and s.st_uid==os.geteuid() and stat.S_ISREG(s.st_mode)
 refs=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   if str(p) in (proc/'maps').read_text():refs.append(int(proc.name))
   for fd in (proc/'fd').iterdir():
    try:
     if os.readlink(fd)==str(p):refs.append(int(proc.name))
    except FileNotFoundError:pass
  except (FileNotFoundError,ProcessLookupError):pass
 assert not refs,refs
 h=hashlib.sha256();size=0
 with p.open('rb') as src,tmp.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=6,mtime=0) as dst:
  for b in iter(lambda:src.read(8*1024**2),b''):h.update(b);size+=len(b);dst.write(b)
 assert {'bytes':size,'sha256':h.hexdigest()}==want
 hr=hashlib.sha256();restored=0
 with gzip.open(tmp,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):hr.update(b);restored+=len(b)
 assert {'bytes':restored,'sha256':hr.hexdigest()}==want
 now=p.stat();assert (now.st_dev,now.st_ino,now.st_size,now.st_mtime_ns)==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
 os.replace(tmp,z)
 row={'original_relative_path':rel,'original_bytes':size,'original_sha256':h.hexdigest(),'compressed_bytes':z.stat().st_size,'compressed_sha256':hashlib.sha256(z.read_bytes()).hexdigest(),'decompression_sha_match':True,'active_refs':refs,'canonical_raw_copy_retained_locally':True}
 # Removing the duplicate raw representation only; all bytes remain exactly recoverable
 # in this same attempt namespace and in separately SHA-verified local canonical files.
 p.unlink();report['records'].append(row)
report['after_free_bytes']=shutil.disk_usage(r).free;report['lossless_bytes_saved']=report['after_free_bytes']-report['before_free_bytes']
with (r/'evidence/COMPLETED_S0_LOG_LOSSLESS_ARCHIVE.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
'''.replace('PROOF',repr(proof))
a=call('R3_COMPLETED_S0_LOG_LOSSLESS_ARCHIVE_01',code,timeout=600)
(ROOT/'evidence/R3_COMPLETED_S0_LOG_LOSSLESS_ARCHIVE.json').write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
