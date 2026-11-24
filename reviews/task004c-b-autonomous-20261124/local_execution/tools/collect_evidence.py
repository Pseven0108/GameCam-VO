import base64,hashlib,io,json,pathlib,zipfile
from remote_cpu import ROOT,call
code=r'''
import pathlib,json,zipfile,io,base64,hashlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
files=[]
for name in ('evidence','artifacts','cpu_tests','operational'):
 for p in (r/name).rglob('*'):
  if p.is_file() and p.suffix.lower() in ('.json','.txt','.md','.csv','.py','.patch'):
   files.append(p)
for n in ('TASK004C_B_AUTONOMOUS_RUN_STATE.json','TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md','source_candidate/native_control/snapshot.py','source_candidate/native_control/metric3d_identity.py'):
 files.append(r/n)
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(set(files)):z.writestr(p.relative_to(r).as_posix(),p.read_bytes())
raw=buf.getvalue();out=r/'operational/EVIDENCE_ONLY.zip';out.write_bytes(raw)
print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'file_count':len(set(files)),'zip_base64':base64.b64encode(raw).decode()}))
'''
d=json.loads(call('COLLECT_FINAL_PRIVATE_EVIDENCE_ONLY',code,timeout=180))
raw=base64.b64decode(d.pop('zip_base64'));assert hashlib.sha256(raw).hexdigest()==d['sha256']
(ROOT/'RAW_REMOTE_EVIDENCE.zip').write_bytes(raw)
dest=ROOT/'remote_evidence';dest.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 assert z.testzip() is None
 for n in z.namelist():
  rel=pathlib.PurePosixPath(n);assert not rel.is_absolute() and '..' not in rel.parts
  p=dest/pathlib.Path(*rel.parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
(ROOT/'evidence/REMOTE_EVIDENCE_TRANSPORT_VERIFICATION.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d,indent=2))
