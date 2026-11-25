"""Inspect JSON, archive directories and NumPy headers; no tensor deserialization."""
import os,sys,pathlib,json,tarfile,hashlib,csv,zipfile,collections,io
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
EXP=ROOT.parent
A=EXP/'GAMECAM_TASK005A_D_SCHEDULE_MECHANISM_20261125_R1'
OLD=EXP/'DROID_W_TASK004C_B_IO_COMPAT_20261124_R1'
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
def dump(name,value):
 (ROOT/'00_intake'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
seal=json.loads((A/'00_seal/TASK004CB_IMMUTABLE_SEAL.json').read_text())
bad=[]
for path,want in seal['complete_metadata_inventory'].items():
 p=pathlib.Path(path)
 if not p.exists() or p.stat().st_size!=want['bytes'] or p.stat().st_mtime_ns!=want['mtime_ns']:bad.append(path)
hashbad=[p for p,v in seal['selected_content_hashes'].items() if sha(pathlib.Path(p))!=v['sha256']]
dump('SEALED_HISTORY_CHECK.json',{'metadata_entries':len(seal['complete_metadata_inventory']),'content_hash_entries':len(seal['selected_content_hashes']),'metadata_mismatch':bad,'content_mismatch':hashbad})
assert not bad and not hashbad
tar=RECEIVER/'C0_IMMUTABLE_LOCAL_BACKUP.tar'
with tarfile.open(tar,'r:') as tf:
 members=tf.getmembers()
 catalog=[{'path':m.name,'bytes':m.size,'regular_file':m.isfile()} for m in members]
 dump('C0_ARCHIVE_DIRECTORY.json',{'archive_bytes':tar.stat().st_size,'members':catalog,'payload_deserialized':False})
 candidates=[m for m in members if m.name.endswith('/manifest.json')]
 for m in candidates:
  if m.size<20*1024**2:
   obj=json.load(tf.extractfile(m));dump('C0_MANIFEST_INTAKE.json',obj)
 print('C0 members',len(members),'JSON',[(m.name,m.size) for m in members if m.name.endswith('.json')][:20])
evidence={}
for arm in ('B1','B2','B4','B3'):
 p=OLD/'raw_evidence/R3_OFFLINE/attempts'/arm
 if not p.exists():p=RECEIVER/'raw_evidence/R3_OFFLINE/attempts'/arm
 types=collections.Counter();examples={};before=[]
 with (p/'observer.jsonl').open() as f:
  for line in f:
   row=json.loads(line);kind=row.get('type','unknown');types[kind]+=1
   if kind not in examples:examples[kind]=row
   if row.get('trigger_rgb_id') in (19,233,401) and 'before' in str(kind):before.append(row)
 npzs={}
 for q in p.rglob('*.npz'):
  with zipfile.ZipFile(q) as z:
   npzs[str(q.relative_to(p))]=[i.filename for i in z.infolist()]
 evidence[arm]={'files':[str(q.relative_to(p)) for q in p.rglob('*') if q.is_file()], 'observer_type_counts':types,'observer_examples':examples,'candidate_before_rows':before,'npz_members':npzs}
 print(arm,'types',types,'candidate before',len(before),'npz',npzs)
dump('BA_EVIDENCE_INVENTORY.json',evidence)
print('seal PASS')
