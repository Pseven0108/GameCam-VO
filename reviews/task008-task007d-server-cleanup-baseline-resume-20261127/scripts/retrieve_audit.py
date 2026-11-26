"""Recover full cleanup manifests privately; verify streamed bytes on the local CPU."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
from transport import ROOT,mod

remote_root='/root/rivermind-data/GAMECAM_TASK008_TASK007D_CLEANUP_20261127'
allowed=['CLEANUP_AUTHORIZATION_PLAN.json','PROTECTED_FILES_BEFORE.json','DELETION_INVENTORY_BEFORE.json',
         'RESOURCE_BEFORE.json','PROGRESS.json','PROTECTED_FILES_AFTER.json','STAGE_DISPOSITION.json','CLEANUP_FINAL_RECEIPT.json']
script='''import hashlib,json,pathlib
w=pathlib.Path(ROOT)
print(json.dumps({'files':[{'path':n,'bytes':(w/n).stat().st_size,'sha256':hashlib.sha256((w/n).read_bytes()).hexdigest()} for n in NAMES]}))
'''.replace('ROOT',repr(remote_root)).replace('NAMES',repr(allowed))
manifest=json.loads(mod.run(script,'AUDIT_COLLECTION_MANIFEST',timeout=60))
out=ROOT/'remote_audit';out.mkdir(exist_ok=False)
rows={r['path']:r for r in manifest['files']}
script='''import pathlib,sys,tarfile
w=pathlib.Path(ROOT)
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for n in NAMES:t.add(w/n,arcname=n,recursive=False)
'''.replace('ROOT',repr(remote_root)).replace('NAMES',repr(allowed))
with (ROOT/'logs/AUDIT_TRANSFER.stderr.txt').open('xb') as err:
    p=subprocess.Popen([str(mod.SSH),'-T','-p',mod.PORT,*mod.options(),'root@'+mod.ENDPOINT,
                         'exec /usr/bin/python3 -B -c '+shlex.quote(script)],stdout=subprocess.PIPE,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    with tarfile.open(fileobj=p.stdout,mode='r|') as t:
        for m in t:
            assert m.isfile() and m.name in rows
            data=t.extractfile(m).read();r=rows[m.name]
            assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
            with (out/m.name).open('xb') as f:f.write(data)
    assert p.wait(timeout=60)==0
assert set(x.name for x in out.iterdir())==set(allowed)
(ROOT/'AUDIT_TRANSFER_VERIFIED.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'files_verified':len(allowed),'bytes':sum(r['bytes'] for r in rows.values()),'SHA256':'PASS'}))
