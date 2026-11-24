"""Read-only stream of the existing C0 to a verified local archive; no GPU or remote tar file."""
import pathlib,json,subprocess,os,time,hashlib,tarfile,shutil
from remote import ROOT,transport
BASE=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
OUT=BASE/'C0_IMMUTABLE_LOCAL_BACKUP.tar';assert not OUT.exists()
assert shutil.disk_usage(BASE).free>14*1024**3
pre=transport.pre;base=transport.ssh.ssh_base(pre);base[base.index('-p')+1]='30448'
code=r'''
import pathlib,tarfile,sys,os
p=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/C0');assert p.is_dir()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as tf:
 for f in sorted(p.rglob('*')):
  if f.is_file():
   assert not f.is_symlink() and f.resolve().is_relative_to(p.resolve())
   tf.add(f,arcname='C0/'+f.relative_to(p).as_posix(),recursive=False)
'''
err=ROOT/'evidence/R3_C0_LOCAL_BACKUP.stderr.txt';start=time.time()
with OUT.open('xb') as of,err.open('xb') as ef:q=subprocess.run(base+['-o','ClearAllForwardings=yes',transport.ssh.HOST,'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -'],input=code.encode(),stdout=of,stderr=ef,timeout=600,creationflags=transport.ssh.CREATE)
assert q.returncode==0 and all(transport.ssh.verified(err).values())
observed={};manifest=None
with tarfile.open(OUT,'r:') as tf:
 for m in tf:
  assert m.isfile() and m.name.startswith('C0/') and '..' not in pathlib.PurePosixPath(m.name).parts
  h=hashlib.sha256();n=0;chunks=[] if m.name=='C0/manifest.json' else None
  with tf.extractfile(m) as f:
   for b in iter(lambda:f.read(8*1024**2),b''):
    h.update(b);n+=len(b)
    if chunks is not None:chunks.append(b)
  observed[m.name[3:]]={'sha256':h.hexdigest(),'bytes':n}
  if chunks is not None:manifest=json.loads(b''.join(chunks))
assert manifest and manifest['state_sha256']=='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
checks={n:n in observed and observed[n]['sha256']==v['sha256'] and (v.get('bytes',v.get('size')) is None or observed[n]['bytes']==v.get('bytes',v.get('size'))) for n,v in manifest['files'].items()}
assert any(v['sha256']==manifest['state_sha256'] for v in observed.values()),'C0 state content hash missing'
assert checks and all(checks.values()),[n for n,v in checks.items() if not v][:3]
h=hashlib.sha256()
with OUT.open('rb') as f:
 for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
result={'start_unix':start,'end_unix':time.time(),'CPU_only':True,'new_C0_captured':False,'remote_files_modified':False,'remote_temporary_archive_created':False,'archive_path':str(OUT),'archive_bytes':OUT.stat().st_size,'archive_sha256':h.hexdigest(),'archive_members':len(observed),'manifest_files_checked':len(checks),'all_member_SHA_match':True,'C0_state_sha256':manifest['state_sha256'],'remote_tar_stream_exit_code':q.returncode,'trust':transport.ssh.verified(err),'original_C0_preserved':True}
(ROOT/'evidence/R3_C0_LOCAL_BACKUP_VERIFICATION.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
