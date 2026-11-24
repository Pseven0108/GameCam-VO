"""Reclaim only this failed capture's verified all-zero temporary backing files."""
import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,os,pathlib,shutil,stat,subprocess
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1')
post=json.loads((root/'artifacts/C0_POSTMORTEM.json').read_text());out=root/'attempts/capture'
assert post['GPU_process_exit_code']==1 and post['tracking_frames_admitted']==0 and not (root/'C0').exists()
assert not post['remaining_own_process_group'] and not post['live_backing_maps'] and not post['proc_maps_permission_errors']
arena=out/'shared_cpu';expected=post['backing_files']
assert arena.resolve().parent==out.resolve() and not arena.is_symlink()
assert {p.name for p in arena.iterdir()}=={pathlib.Path(r['path']).name for r in expected}
assert sorted(r['bytes'] for r in expected)==[864000000,1382400000]
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def zero_sha(n):
 h=hashlib.sha256();b=b'\0'*(8*1024**2)
 while n:
  take=min(n,len(b));h.update(memoryview(b)[:take]);n-=take
 return h.hexdigest()
maps=[];errors=[];pgroup=[]
pgid=json.loads((out/'PROCESS_STARTED.json').read_text())['pgid']
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  text=(proc/'maps').read_text()
  if str(arena)+'/' in text:maps.append(int(proc.name))
  raw=(proc/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
  if int(fields[2])==pgid:pgroup.append(int(proc.name))
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:errors.append(int(proc.name))
assert not maps and not errors and not pgroup
for row in expected:
 p=pathlib.Path(row['path']);s=p.lstat()
 assert p.parent==arena and p.name==str(row['inode'])+'.bin' and not p.is_symlink()
 assert stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o600 and s.st_uid==os.getuid()
 assert (s.st_dev,s.st_ino,s.st_size)==(row['st_dev'],row['inode'],row['bytes'])
 assert sha(p)==row['sha256']==zero_sha(row['bytes']),'Preserve nonzero forensic storage'
before=shutil.disk_usage(root).free
for row in expected:
 p=pathlib.Path(row['path']);s=p.lstat()
 assert (s.st_dev,s.st_ino,s.st_size)==(row['st_dev'],row['inode'],row['bytes'])
 p.unlink()
after=shutil.disk_usage(root).free
lock=json.loads((root/'configs/identity_lock.json').read_text());protected={}
for name,expected_sha in {**lock['remote_pins'],**lock['execution_source_pins']}.items():
 actual=sha(name);assert actual==expected_sha;protected[name]={'expected':expected_sha,'actual':actual,'match':True}
result={'cleanup_scope':'Only two newly created all-zero failed-attempt arena files',
 'all_files_verified_all_zero':True,'same_owner_inode_device_size_mode_sha_verified':True,
 'related_processes_exited':True,'no_proc_maps_references':True,'permission_failures':[],
 'removed_files':expected,'logical_bytes_removed':sum(r['bytes'] for r in expected),
 'free_bytes_before':before,'free_bytes_after':after,'observed_free_increase':after-before,
 'historical_files_deleted':0,'logs_receipts_recordings_and_diagnosis_preserved':True,
 'protected_pins_after':protected,'source_commit_after':subprocess.check_output(['git','-C',str(root/'source_candidate'),'rev-parse','HEAD'],text=True).strip(),
 'tracked_source_status_after':subprocess.check_output(['git','-C',str(root/'source_candidate'),'status','--porcelain','--untracked-files=no'],text=True),
 'original_reviewed_source_status_after':subprocess.check_output(['git','-C','/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1/source_candidate','status','--porcelain','--untracked-files=no'],text=True),
 'new_native_lifecycles':0,'GPU_retried':False,'server_shutdown':False}
with (root/'artifacts/OWNED_ARENA_CLEANUP.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
'''
d=json.loads(call('CLEAN_OWNED_ZERO_ARENA',code,timeout=180))
(ROOT/'evidence/OWNED_ARENA_CLEANUP.json').write_text(json.dumps(d,indent=2))
print(json.dumps({k:v for k,v in d.items() if k not in ('protected_pins_after','removed_files')}))
