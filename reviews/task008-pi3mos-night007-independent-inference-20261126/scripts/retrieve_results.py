"""Stream only inventoried TASK008 evidence to local storage and verify every file."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import shlex
import subprocess
import tarfile
import time

from remote_transport import run,ROOT,SSH,PORT,ENDPOINT,options

W='/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED'
script='from pathlib import Path;print(Path('+repr(W+'/RESULT_COLLECTION_MANIFEST.json')+').read_text())'
manifest=json.loads(run(script,'RESULT_COLLECTION_MANIFEST_READBACK',timeout=60))
rows={r['path']:r for r in manifest['files']}
assert all(PurePosixPath(p).is_relative_to('.') and '..' not in PurePosixPath(p).parts for p in rows)
dest=ROOT/'retrieved';dest.mkdir(exist_ok=False)
remote='''import json,pathlib,sys,tarfile
w=pathlib.Path(WORK)
data=json.loads((w/'RESULT_COLLECTION_MANIFEST.json').read_text())
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for row in data['files']:t.add(w/row['path'],arcname=row['path'],recursive=False)
'''.replace('WORK',repr(W))
command='exec /usr/bin/python3 -B -c '+shlex.quote(remote)
start=time.perf_counter();verified=[]
with (ROOT/'logs/RESULT_TRANSFER.stderr.txt').open('xb') as err:
    p=subprocess.Popen([str(SSH),'-T','-p',PORT,*options(),'root@'+ENDPOINT,command],stdout=subprocess.PIPE,stderr=err,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        with tarfile.open(fileobj=p.stdout,mode='r|') as archive:
            for member in archive:
                assert member.isfile() and member.name in rows
                r=rows[member.name];assert member.size==r['bytes']
                target=dest.joinpath(*PurePosixPath(member.name).parts)
                assert target.resolve().is_relative_to(dest.resolve())
                target.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();count=0
                with archive.extractfile(member) as stream,target.open('xb') as f:
                    for b in iter(lambda:stream.read(4*1024**2),b''):h.update(b);f.write(b);count+=len(b)
                assert count==r['bytes'] and h.hexdigest()==r['sha256']
                verified.append(member.name)
        assert p.wait(timeout=60)==0
    finally:
        if p.poll() is None:p.terminate()
assert set(verified)==set(rows) and len(verified)==len(rows)
with (dest/'RESULT_COLLECTION_MANIFEST.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2);f.write('\n')
receipt={'files_verified':len(verified),'bytes':sum(r['bytes'] for r in rows.values()),'SHA256':'ALL PASS',
         'seconds':time.perf_counter()-start,'remote_originals_preserved':True,'model_weights_transferred_in_result_package':False}
with (ROOT/'logs/RESULT_TRANSFER_VERIFICATION.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt,indent=2))
