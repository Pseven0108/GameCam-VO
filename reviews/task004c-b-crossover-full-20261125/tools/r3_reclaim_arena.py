"""Reclaim only a successful current-task arena after zero active mappings."""
import json,sys
from remote import ROOT,call
mode=sys.argv[1]
assert mode in ('B1','B2','B4','B3')
code=r'''
import os,pathlib,json,stat,hashlib,shutil,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');mode=MODE
out=r/'attempts'/mode
assert out.resolve()==out and not out.is_symlink()
receipt=json.loads((out/'PROCESS_RECEIPT.json').read_text());success=json.loads((out/'SUCCESS.json').read_text())
assert receipt['exit_code']==0 and receipt['success_receipt_exists'] and success['mode']==mode
pid=success['pid']
try:assert pathlib.Path('/proc',str(pid),'stat').read_text().split()[2]=='Z','stage process still alive'
except FileNotFoundError:pass
suffix=hashlib.sha256(str(r).encode()).hexdigest()[:12]
arena=pathlib.Path('/dev/shm/gamecam_task004cb_io_r3')/(suffix+'_'+mode)
assert arena.is_dir() and not arena.is_symlink() and arena.resolve()==arena
assert arena.parent==pathlib.Path('/dev/shm/gamecam_task004cb_io_r3') and arena.name.endswith('_'+mode)
paths=list(arena.iterdir());assert paths and all(p.is_file() and not p.is_symlink() and p.suffix=='.bin' for p in paths)
files=[]
for p in paths:
 s=p.stat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 files.append({'name':p.name,'bytes':s.st_size,'dev':s.st_dev,'ino':s.st_ino,'uid':s.st_uid,'sha256':h.hexdigest()})
refs=[];scan_errors=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  maps=(proc/'maps').read_text()
  if str(arena) in maps:refs.append({'pid':int(proc.name),'type':'maps'})
  for fd in (proc/'fd').iterdir():
   try:
    if os.readlink(fd).startswith(str(arena)+'/'):refs.append({'pid':int(proc.name),'type':'fd'})
   except FileNotFoundError:pass
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:scan_errors.append(int(proc.name))
assert not refs and not scan_errors,{'active':refs,'errors':scan_errors}
report={'mode':mode,'success_exit_verified':True,'active_mapping_refs':refs,'scan_errors':scan_errors,'files':files,'before_free_bytes':shutil.disk_usage(arena.parent).free,'time_unix':time.time(),'scope':'successful current-task temporary arena only','historical_files_deleted':0}
evidence=r/'evidence'/('ARENA_RECLAIM_'+mode+'.json')
with evidence.open('x') as f:json.dump(report,f,indent=2)
for x in files:
 p=arena/x['name'];s=p.stat();assert (s.st_dev,s.st_ino,s.st_size,s.st_uid)==(x['dev'],x['ino'],x['bytes'],x['uid'])
 p.unlink()
arena.rmdir()
report['after_free_bytes']=shutil.disk_usage(arena.parent).free;report['reclaimed_bytes']=sum(x['bytes'] for x in files);report['completed']=True
evidence.write_text(json.dumps(report,indent=2));print(json.dumps(report))
'''.replace('MODE',repr(mode))
a=call('R3_ARENA_RECLAIM_'+mode,code,timeout=240)
(ROOT/'evidence'/('R3_ARENA_RECLAIM_'+mode+'.json')).write_text(json.dumps(a,indent=2))
print(json.dumps(a,indent=2))
