"""Reversible exact-copy spool for completed current-task logs, preserving logical paths."""
import json,hashlib,sys
from remote import ROOT,call
mode=sys.argv[1];index=sys.argv[2] if len(sys.argv)>2 else '01'
assert mode in ('B1','B2','B4')
proof=json.loads((ROOT/'evidence'/('R3_COLLECTION_'+mode+('_02.json' if mode=='B1' else '_01.json'))).read_text())
assert proof['receipt']['all_file_hashes_match']
code=r'''
import os,pathlib,json,hashlib,shutil,stat,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');mode=MODE
out=r/'attempts'/mode;spool=pathlib.Path('/root/gamecam-task004cb-r3-completed-spool')/mode
assert json.loads((out/'PROCESS_RECEIPT.json').read_text())['exit_code']==0 and (out/'SUCCESS.json').is_file()
assert not spool.exists();spool.mkdir(parents=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
report={'scope':'COMPLETED_CURRENT_TASK_LOGS_ONLY','temporary_system_volume_spool':True,'local_raw_and_archive_verified':True,'historical_files_touched':False,'before_data_free':shutil.disk_usage(r).free,'before_system_free':shutil.disk_usage(spool).free,'files':[],'unix':time.time()}
for name in (('rerun_stream.rrd.gz','native/video.npz') if mode=='B4' else ('rerun_stream.rrd.gz','rerun_stream.rrd','native/video.npz','schedule.jsonl.gz','observer.jsonl.gz')):
 src=out/name
 if not src.is_file():continue
 assert not src.is_symlink() and src.resolve().is_relative_to(r/'attempts'/mode)
 st=src.stat();assert stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.geteuid()
 refs=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   if str(src) in (proc/'maps').read_text():refs.append(int(proc.name))
   for fd in (proc/'fd').iterdir():
    try:
     if os.readlink(fd)==str(src):refs.append(int(proc.name))
    except FileNotFoundError:pass
  except (FileNotFoundError,ProcessLookupError):pass
 assert not refs,refs
 assert shutil.disk_usage(spool).free>st.st_size+2*1024**3
 dst=spool/name;dst.parent.mkdir(exist_ok=True,parents=True);assert not dst.exists()
 expected=sha(src);shutil.copy2(src,dst);assert sha(dst)==expected and dst.stat().st_size==st.st_size
 now=src.stat();assert (now.st_ino,now.st_dev,now.st_size,now.st_mtime_ns)==(st.st_ino,st.st_dev,st.st_size,st.st_mtime_ns)
 link=src.with_name(src.name+'.spool-link');assert not link.exists();link.symlink_to(dst)
 os.replace(link,src);assert src.is_symlink() and sha(src)==expected
 report['files'].append({'logical_path':str(src.relative_to(r)),'spool_path':str(dst),'bytes':st.st_size,'sha256':expected,'logical_path_readback_matches':True,'active_refs':refs,'rollback':'Copy verified spool bytes back to data-volume path atomically only when enough capacity is available'})
report['after_data_free']=shutil.disk_usage(r).free;report['after_system_free']=shutil.disk_usage(spool).free
receipt=r/'evidence'/('COMPLETED_LOG_SPOOL_'+mode+'.json');assert not receipt.exists();receipt.write_text(json.dumps(report,indent=2));print(json.dumps(report))
'''.replace('MODE',repr(mode))
a=call('R3_COMPLETED_LOG_SPOOL_'+mode+'_'+index,code,timeout=300)
(ROOT/'evidence'/('R3_COMPLETED_LOG_SPOOL_'+mode+'_'+index+'.json')).write_text(json.dumps(a,indent=2));print(json.dumps(a,indent=2))
