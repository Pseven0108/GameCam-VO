"""Stream the sealed public review to the authorized server without copying credentials."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import zipfile

from remote_transport import ROOT,PROJECT,SSH,PORT,ENDPOINT,options

R=PROJECT/'reviews/task008-pi3mos-night007-independent-inference-20261126'
PUB=PROJECT/'maintenance/GITHUB_TASK008_PUBLICATION_20261126'
receipt=json.loads((R/'deliveries/PACKAGE_VERIFICATION.json').read_text())
archive=R/'deliveries'/receipt['ZIP_name'];raw=archive.read_bytes()
assert len(raw)==receipt['ZIP_bytes'] and hashlib.sha256(raw).hexdigest()==receipt['ZIP_sha256']

def row(path,b):return {'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'base64':base64.b64encode(b).decode()}

files=[]
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name in z.namelist():
        b=z.read(name);assert b==(R/name).read_bytes();files.append(row(name,b))
for name in ['deliveries/PACKAGE_VERIFICATION.json','deliveries/'+archive.name+'.sha256']:files.append(row(name,(R/name).read_bytes()))
project=[]
for p in sorted((ROOT/'scripts').glob('*.py')):project.append(row('experiments/task008_pi3mos/scripts/'+p.name,p.read_bytes()))
for p in sorted((ROOT/'configs').glob('*.json')):project.append(row('experiments/task008_pi3mos/configs/'+p.name,p.read_bytes()))
for name in ['README.md','environment_notes.md','reports/TASK008_REPORT.md']:project.append(row('experiments/task008_pi3mos/'+name,(ROOT/name).read_bytes()))
states=[]
for r in json.loads((R/'project_entries/ENTRY_UPDATE_PLAN.json').read_text())['files']:
    states.append({**row(r['path'],(R/r['source_file']).read_bytes()),'base_sha':r['base_git_blob_sha']})
payload={'files':files,'project_files':project,'state_entries':states,'ZIP':receipt,'ZIP_base64':base64.b64encode(raw).decode()}
remote=(ROOT/'scripts/remote_publish_review.py').read_text('utf-8')
command='exec env PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES= /usr/bin/python3 -B -u -c '+shlex.quote(remote)
with (PUB/'PUBLISH.stdout.txt').open('xb') as out,(PUB/'PUBLISH.stderr.txt').open('xb') as err:
    p=subprocess.run([str(SSH),'-T','-p',PORT,*options(),'root@'+ENDPOINT,command],input=json.dumps(payload).encode(),
                     stdout=out,stderr=err,timeout=1500,creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode==0,'Publication interrupted: inspect saved remote progress; do not rerun full task or change visibility'
result=json.loads((PUB/'PUBLISH.stdout.txt').read_text())
with (PUB/'PUBLICATION_RECEIPT.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='expanded_files'},indent=2))
