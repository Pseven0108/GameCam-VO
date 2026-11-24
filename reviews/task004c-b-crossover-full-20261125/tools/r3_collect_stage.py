"""Transfer completed stage evidence through strict pinned SSH, excluding arenas/C0."""
import hashlib,json,pathlib,shutil,subprocess,sys,tarfile,time
from remote import ROOT,call,transport
mode=sys.argv[1]; index=sys.argv[2] if len(sys.argv)>2 else '01'
assert mode in ('restore_check','record_S1','replay_D0_S1','record_S0','replay_D1_S0','B1','B2','B4','B3')
code=r'''
import pathlib,json,hashlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');mode=MODE
out=r/'attempts'/mode
assert (out/'PROCESS_RECEIPT.json').is_file()
files={}
for base in (out,r/'artifacts'/('STAGE_'+mode)):
 for p in sorted(base.rglob('*')):
  rel=p.relative_to(r)
  if not p.is_file() or p.is_symlink() or 'shared_cpu' in rel.parts or p.suffix in ('.bin','.pt'):continue
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
  files[rel.as_posix()]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
print(json.dumps({'mode':mode,'files':files,'total_bytes':sum(v['bytes'] for v in files.values())}))
'''.replace('MODE',repr(mode))
a=call('R3_COLLECT_INVENTORY_'+mode+'_'+index,code,timeout=120)
from evidence_locations import EXTERNAL_ROOT
base=(EXTERNAL_ROOT if mode in ('B4','B3') else ROOT)/'raw_evidence'/'R3_OFFLINE'
base.mkdir(exist_ok=True,parents=True)
# Newly collected archives may use the larger local C: volume; canonical evidence
# remains in the experiment workspace. No historical files are moved or removed.
packdir=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\stage_archives') if mode in ('B4','B3') else ROOT/'stage_archives'
packdir.mkdir(exist_ok=True,parents=True)
archive=packdir/('R3_'+mode+'_collection'+index+'.tar.gz')
assert not archive.exists()
same_volume=packdir.drive.lower()==base.drive.lower()
need_pack=(2 if same_volume else 1)*a['total_bytes']+1024**3
assert shutil.disk_usage(packdir).free>need_pack,'Insufficient local archive plus extraction reserve'
assert same_volume or shutil.disk_usage(base).free>a['total_bytes']+1024**3,'Insufficient canonical evidence reserve'
basecmd=transport.ssh.ssh_base(transport.pre);basecmd[basecmd.index('-p')+1]='30448'
script=r'''
import pathlib,sys,tarfile,hashlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
files=FILES
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as tf:
 for n,info in files.items():
  p=r/n;assert p.is_file() and not p.is_symlink() and p.stat().st_size==info['bytes']
  tf.add(p,arcname=n,recursive=False)
'''.replace('FILES',repr(a['files']))
err=ROOT/'transport'/('R3_DOWNLOAD_'+mode+'_'+index+'.stderr.txt')
start=time.time()
with archive.open('xb') as of,err.open('xb') as ef:
 p=subprocess.run(basecmd+['-o','ClearAllForwardings=yes',transport.ssh.HOST,'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -'],input=script.encode(),stdout=of,stderr=ef,timeout=600,creationflags=transport.ssh.CREATE)
receipt={'mode':mode,'local_archive_path':str(archive),'local_canonical_root':str(base),'exit_code':p.returncode,'trust':transport.ssh.verified(err),'start_unix':start,'end_unix':time.time(),'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
assert p.returncode==0 and all(receipt['trust'].values()),receipt
with tarfile.open(archive,'r:gz') as tf:
 members=tf.getmembers();assert {x.name for x in members}==set(a['files'])
 for m in members:
  assert m.isfile() and not pathlib.PurePosixPath(m.name).is_absolute() and '..' not in pathlib.PurePosixPath(m.name).parts
  raw=tf.extractfile(m).read();assert len(raw)==a['files'][m.name]['bytes'] and hashlib.sha256(raw).hexdigest()==a['files'][m.name]['sha256']
  target=base/pathlib.PurePosixPath(m.name);target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(raw)
receipt.update(files_verified=len(a['files']),all_file_hashes_match=True)
(ROOT/'evidence'/('R3_COLLECTION_'+mode+'_'+index+'.json')).write_text(json.dumps({'receipt':receipt,'inventory':a},indent=2))
print(json.dumps(receipt,indent=2))
