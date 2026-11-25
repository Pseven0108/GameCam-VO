"""Copy only this task's run logs/receipts after GPU work is terminal."""
import pathlib,sys,subprocess,json,tarfile,hashlib,io,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'01_runtime'))
from ssh_execute import base,ssh
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
CODE=r'''
import pathlib,sys,tarfile,hashlib,json,io,subprocess,time
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1').resolve()
stop_mode=False
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
for arm in (('D1_S1','D0_S1') if stop_mode else ('D1_S1','D0_S1','D1_S0','D0_S0')):
 assert json.loads((r/'attempts'/arm/'PROCESS_RECEIPT.json').read_text())['exit_code']==0
 if not stop_mode:assert json.loads((r/'retirement'/(arm+'.json')).read_text())['completed']
if stop_mode:
 assert not (r/'attempts/D1_S0').exists() and not (r/'attempts/D0_S0').exists()
 assert json.loads((r/'evidence/REPLAY_CONTEXT02_D0_S1_RGB233/PROCESS_RECEIPT.json').read_text())['exit_code']==1
 assert (r/'results_context02/D0_S1_RGB233/ENDPOINT_FAILURE.json').exists()
files=[]
for subdir in ('attempts','evidence','retirement'):
 for path in sorted((r/subdir).rglob('*')):
  if path.is_file():
   assert not path.is_symlink() and path.resolve().is_relative_to(r)
   files.append(path)
for name in ('AUTHORIZATION.json','build_attempt02/BUILD_COMPLETE.json','build_attempt02/build.ninja'):
 if (r/name).is_file():files.append(r/name)
manifest={}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for path in files:
  name=path.relative_to(r).as_posix();before=path.stat();h=hashlib.sha256()
  with path.open('rb') as stream:
   for block in iter(lambda:stream.read(8*1024**2),b''):h.update(block)
  after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  manifest[name]={'bytes':after.st_size,'sha256':h.hexdigest()}
  archive.add(path,arcname=name,recursive=False)
 body=json.dumps({'files':manifest,'unix':time.time(),'historical_files_included':False,'GPU_processes_empty':True},indent=2).encode()
 header=tarfile.TarInfo('TRANSFER_MANIFEST.json');header.size=len(body);archive.addfile(header,io.BytesIO(body))
'''

def main():
    stopped='--stopped' in sys.argv
    if stopped:assert 'Native endpoint mismatch' in json.loads((ROOT/'04_results/SUPERVISOR_STOP_RESUME02.json').read_text())['error']
    else:assert json.loads((ROOT/'04_results/SUPERVISOR_SUCCESS.json').read_text())['PASS']
    target=RECEIVER/'task005b_run_evidence.tar.gz'
    err=ROOT/'00_intake/COLLECT_RUN_EVIDENCE.stderr.txt'
    with target.open('xb') as out,err.open('xb') as error:
        code=CODE.replace('stop_mode=False','stop_mode=True') if stopped else CODE
        result=subprocess.run(base()+['-o','ClearAllForwardings=yes',ssh.HOST,'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -'],input=code.encode(),stdout=out,stderr=error,timeout=900,creationflags=ssh.CREATE)
    assert result.returncode==0 and all(ssh.verified(err).values())
    members={}
    with tarfile.open(target,'r:gz') as archive:
        for entry in archive:
            if not entry.isfile():continue
            path=pathlib.PurePosixPath(entry.name)
            assert not path.is_absolute() and '..' not in path.parts
            if entry.name=='TRANSFER_MANIFEST.json':manifest=json.load(archive.extractfile(entry));continue
            h=hashlib.sha256()
            with archive.extractfile(entry) as stream:
                for block in iter(lambda:stream.read(8*1024**2),b''):h.update(block)
            members[entry.name]={'bytes':entry.size,'sha256':h.hexdigest()}
    assert members==manifest['files']
    digest=hashlib.sha256()
    with target.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024**2),b''):digest.update(block)
    proof={'archive':str(target),'bytes':target.stat().st_size,'sha256':digest.hexdigest(),'members':members,'SSH_trust':ssh.verified(err),'all_member_SHA_verified':True,'remote_sources_removed':False}
    (ROOT/'07_release/RUN_EVIDENCE_TRANSFER.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps({k:v for k,v in proof.items() if k!='members'}))

if __name__=='__main__':main()
