"""Back up inactive installer cache and remove verified remote duplicate files only."""
import hashlib,json,os,pathlib,shutil,subprocess,tarfile,time
from remote import ROOT,call,transport
from evidence_locations import EXTERNAL_ROOT
out=EXTERNAL_ROOT/'cache_backup_20261125'
out.mkdir(parents=True,exist_ok=False)
source=json.loads((ROOT/'evidence/R3_INSTALLER_CACHE_STORAGE_RESCUE_01.json').read_text())
files=source['files']
assert len(files)==14 and sum(x['bytes'] for x in files)==2134549899
assert shutil.disk_usage(out).free>sum(x['bytes'] for x in files)+5*1024**3
basecode=r'''
import pathlib,os,json,hashlib,stat,shutil,time
files=FILES
cache=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/download_cache/conda-pkgs')
spool=pathlib.Path('/root/gamecam-task004cb-r3-completed-spool/unused_installer_archives')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def refs(p):
 found=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   if str(p) in (proc/'maps').read_text():found.append(proc.name+':map')
   for fd in (proc/'fd').iterdir():
    try:
     if os.readlink(fd)==str(p):found.append(proc.name+':fd')
    except (FileNotFoundError,ProcessLookupError):pass
  except (FileNotFoundError,ProcessLookupError):pass
 return found
checked=[]
for row in files:
 logical=pathlib.Path(row['path']);p=pathlib.Path(row['new_backing'])
 assert logical.parent.resolve()==cache.resolve() and p.parent.resolve()==spool.resolve()
 assert p.name==logical.name and p.name.endswith('.tar.bz2')
 assert logical.is_symlink() and logical.resolve()==p.resolve()
 assert not p.is_symlink() and p.resolve().parent==spool.resolve()
 st=p.stat();assert stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.geteuid()
 assert st.st_size==row['bytes'] and sha(p)==row['sha256']
 active=refs(p);assert not active,active
 checked.append(dict(row,identity=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns],active_refs=active))
'''.replace('FILES',repr(files))
pre=call('R3_INSTALLER_LOCAL_BACKUP_PREFLIGHT_01',basecode+"\nprint(json.dumps({'files':checked,'data_free':shutil.disk_usage(cache).free,'root_free':shutil.disk_usage(spool).free,'unix':time.time()}))",timeout=240)
(out/'REMOTE_PREFLIGHT.json').write_text(json.dumps(pre,indent=2))
base=transport.ssh.ssh_base(transport.pre);base[base.index('-p')+1]='30448'
stream=r'''
import pathlib,sys,tarfile
files=FILES
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tf:
 for row in files:
  p=pathlib.Path(row['new_backing']);assert p.is_file() and not p.is_symlink() and p.stat().st_size==row['bytes']
  tf.add(p,arcname=p.name,recursive=False)
'''.replace('FILES',repr(files))
archive=out/'unused_installer_cache_backup.tar';err=out/'SSH_DOWNLOAD.stderr.txt'
start=time.time()
with archive.open('xb') as of,err.open('xb') as ef:
 p=subprocess.run(base+['-o','ClearAllForwardings=yes',transport.ssh.HOST,'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -'],input=stream.encode(),stdout=of,stderr=ef,timeout=1200,creationflags=transport.ssh.CREATE)
trust=transport.ssh.verified(err)
assert p.returncode==0 and all(trust.values()),(p.returncode,trust)
expected={pathlib.PurePosixPath(x['new_backing']).name:x for x in files};verified=[]
with tarfile.open(archive,'r:') as tf:
 members=tf.getmembers();assert len(members)==len(expected) and {m.name for m in members}==set(expected)
 for m in members:
  assert m.isfile() and m.name==pathlib.PurePosixPath(m.name).name
  h=hashlib.sha256();count=0
  with tf.extractfile(m) as f:
   for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);count+=len(b)
  assert count==expected[m.name]['bytes'] and h.hexdigest()==expected[m.name]['sha256']
  verified.append({'member':m.name,'bytes':count,'sha256':h.hexdigest(),'PASS':True})
h=hashlib.sha256()
with archive.open('rb') as f:
 for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
proof={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':h.hexdigest(),'files':verified,'all_14_members_verified':True,'trust':trust,'download_exit_code':p.returncode,'start_unix':start,'verified_unix':time.time(),'original_data_bytes':sum(x['bytes'] for x in files)}
(out/'LOCAL_BACKUP_VERIFICATION.json').write_text(json.dumps(proof,indent=2))
print(json.dumps({'phase':'LOCAL_BACKUP_VERIFIED','files':len(verified),'bytes':proof['original_data_bytes'],'archive':str(archive)}),flush=True)
# Independent final readback and active-file check precede any unlink.
cleanup=basecode+r'''
expected_identity=IDENTITIES
for row in checked:assert row['identity']==expected_identity[row['new_backing']]
report={'scope':'INACTIVE_INSTALLER_CACHE_ONLY','local_backup_verified':True,'local_archive_sha256':ARCHIVESHA,'local_archive_path':ARCHIVEPATH,'before_data_free':shutil.disk_usage(cache).free,'before_root_free':shutil.disk_usage(spool).free,'files':[],'installed_runtime_libraries_touched':False,'models_or_scientific_outputs_deleted':False,'unix':time.time()}
for row in checked:
 p=pathlib.Path(row['new_backing']);logical=pathlib.Path(row['path'])
 st=p.stat();assert [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns]==row['identity']
 assert not refs(p) and logical.is_symlink() and logical.resolve()==p.resolve()
 logical.unlink();p.unlink()
 assert not logical.exists() and not logical.is_symlink() and not p.exists()
 report['files'].append(row)
report.update(after_data_free=shutil.disk_usage(cache).free,after_root_free=shutil.disk_usage(spool).free,bytes_removed=sum(x['bytes'] for x in checked),all_14_backed_up_and_removed=True)
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/evidence/INSTALLER_CACHE_LOCAL_BACKUP_CLEANUP.json')
with r.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
'''
cleanup=cleanup.replace('IDENTITIES',repr({x['new_backing']:x['identity'] for x in pre['files']})).replace('ARCHIVESHA',repr(proof['archive_sha256'])).replace('ARCHIVEPATH',repr(str(archive)))
result=call('R3_INSTALLER_LOCAL_BACKUP_CLEANUP_01',cleanup,timeout=240)
(ROOT/'evidence/R3_INSTALLER_LOCAL_BACKUP_CLEANUP_01.json').write_text(json.dumps(result,indent=2))
(out/'REMOTE_CLEANUP_REPORT.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'phase':'CLEANUP_COMPLETE','files':len(result['files']),'bytes_removed':result['bytes_removed'],'root_free_GiB':result['after_root_free']/1024**3,'data_free_GiB':result['after_data_free']/1024**3,'backup':str(out)},indent=2),flush=True)
