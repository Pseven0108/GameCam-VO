"""One pinned stream; internal member SHA verification and safe extraction."""
import sys,pathlib,json,subprocess,hashlib,tarfile,time,io
from local_remote import bridge,ROOT
phase=sys.argv[1];assert phase in ('plain','trace','final','binary')
recv=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1');recv.mkdir(exist_ok=True)
script='''import pathlib,hashlib,json,tarfile,io,sys
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1')
phase=PHASE
selected=['build/gamecam_task005b_r2_observer.so'] if phase=='binary' else (['results/'+phase,'evidence/'+phase] if phase!='final' else ['build/BUILD_COMPLETE.json','build/build.ninja','candidate','PROTOCOL.md','plain_wrapper.log','build_wrapper.log','trace_wrapper.log','PLAIN_PID.json','BUILD_PID.json','TRACE_PID.json'])
files=[]
for n in selected:
 p=r/n
 if p.is_file():files.append(p)
 elif p.is_dir():files.extend(q for q in p.rglob('*') if q.is_file())
assert files
manifest={str(p.relative_to(r)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
 for p in files:archive.add(p,arcname=str(p.relative_to(r)),recursive=False)
 b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('TRANSFER_MANIFEST.json');info.size=len(b);archive.addfile(info,io.BytesIO(b))
'''.replace('PHASE',repr(phase))
path=recv/(phase+'_evidence.tar');err=ROOT/'00_intake'/(phase+'_TRANSFER.stderr.txt')
cmd='exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -'
start=time.time()
with path.open('xb') as fo,err.open('xb') as fe:
 p=subprocess.run(bridge.base()+['-o','ClearAllForwardings=yes',bridge.ssh.HOST,cmd],input=script.encode(),stdout=fo,stderr=fe,timeout=180,creationflags=bridge.ssh.CREATE)
assert p.returncode==0 and all(bridge.ssh.verified(err).values())
with tarfile.open(path) as archive:
 manifest=json.load(archive.extractfile('TRANSFER_MANIFEST.json'))
 assert set(archive.getnames())==set(manifest)|{'TRANSFER_MANIFEST.json'}
 for name,want in manifest.items():
  m=archive.getmember(name);assert m.isfile() and not name.startswith(('/','\\')) and '..' not in pathlib.PurePosixPath(name).parts
  data=archive.extractfile(m).read();assert len(data)==want['bytes'] and hashlib.sha256(data).hexdigest()==want['sha256']
  dest=recv/'expanded'/name;dest.parent.mkdir(exist_ok=True,parents=True)
  with dest.open('xb') as f:f.write(data)
proof={'archive':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'members':manifest,'all_member_SHA_verified':True,'seconds':time.time()-start,'SSH_trust':bridge.ssh.verified(err)}
(ROOT/'00_intake'/(phase+'_TRANSFER_VERIFICATION.json')).write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='members'},indent=2))
