"""One authenticated evidence stream, member hashes verified before extraction."""
import sys,pathlib,json,subprocess,hashlib,tarfile,time
from local_remote import bridge,ROOT
RECV=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R3-20261125-R1');RECV.mkdir(exist_ok=True)
script='''import pathlib,hashlib,json,tarfile,io,sys
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1')
assert json.loads((r/'results/COMPLETE.json').read_text())['two_iteration_BA_calls']==20
assert json.loads((r/'evidence/run/PROCESS_RECEIPT.json').read_text())['exit_code']==0
selected=['results','evidence','candidate','tools','PROTOCOL.md','build/BUILD_COMPLETE.json','build/build.ninja','build/gamecam_task005b_r3_isolation.so']
files=[]
for n in selected:
 p=r/n
 if p.is_file():files.append(p)
 elif p.is_dir():files.extend(q for q in p.rglob('*') if q.is_file())
manifest={str(p.relative_to(r)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
 for p in files:archive.add(p,arcname=str(p.relative_to(r)),recursive=False)
 b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('TRANSFER_MANIFEST.json');info.size=len(b);archive.addfile(info,io.BytesIO(b))
'''
path=RECV/'r3_evidence.tar';err=ROOT/'00_intake/RESULT_TRANSFER.stderr.txt'
start=time.time();cmd='exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -'
with path.open('xb') as fo,err.open('xb') as fe:
    p=subprocess.run(bridge.base()+['-o','ClearAllForwardings=yes',bridge.ssh.HOST,cmd],input=script.encode(),stdout=fo,stderr=fe,timeout=300,creationflags=bridge.ssh.CREATE)
assert p.returncode==0 and all(bridge.ssh.verified(err).values())
with tarfile.open(path) as archive:
    manifest=json.load(archive.extractfile('TRANSFER_MANIFEST.json'))
    assert set(archive.getnames())==set(manifest)|{'TRANSFER_MANIFEST.json'}
    for name,want in manifest.items():
        member=archive.getmember(name);assert member.isfile() and not name.startswith(('/','\\')) and '..' not in pathlib.PurePosixPath(name).parts
        b=archive.extractfile(member).read();assert len(b)==want['bytes'] and hashlib.sha256(b).hexdigest()==want['sha256']
        dest=RECV/'expanded'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(b)
proof={'archive':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'members':manifest,'all_member_SHA_verified':True,'SSH_trust':bridge.ssh.verified(err),'seconds':time.time()-start}
(ROOT/'00_intake/RESULT_TRANSFER_VERIFICATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='members'},indent=2))
