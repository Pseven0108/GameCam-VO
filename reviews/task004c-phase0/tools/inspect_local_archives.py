import pathlib,sys,os,json,zipfile,hashlib,collections,time,csv
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
B=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z')
t=time.monotonic();out={}
def sha_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
for arm in ['E0','E1']:
 p=next((A/'raw_archives').glob(arm+'_*.zip'))
 r=dict(archive=str(p),bytes=p.stat().st_size,sha256=sha_file(p)); counts=collections.Counter();keys={};samples={};selected=[]
 with zipfile.ZipFile(p) as z:
  r['members']=[dict(name=i.filename,bytes=i.file_size,compressed_bytes=i.compress_size,crc32=f'{i.CRC:08x}') for i in z.infolist()]
  small={}
  for i in z.infolist():
   if i.file_size<200000 and i.filename.endswith(('.json','.yaml')):
    raw=z.read(i)
    try:small[i.filename]=json.loads(raw)
    except:small[i.filename]=raw.decode(errors='replace')
  r['small_metadata']=small
  obs=next(n for n in z.namelist() if n.endswith('observer.jsonl'))
  with z.open(obs) as f:
   for k,line in enumerate(f,1):
    d=json.loads(line);e=d.get('event',d.get('kind',d.get('type','UNKNOWN')));counts[e]+=1;keys.setdefault(e,set()).update(d.keys());samples.setdefault(e,d)
    if d.get('ba_id') in ([550,551,552] if arm=='E0' else [660,661,662]):selected.append(d)
  r.update(observer_member=obs,event_counts=dict(counts),event_keys={k:sorted(v) for k,v in keys.items()},first_event_samples=samples,target_records=selected)
  r['zip_crc_first_bad_member']=z.testzip();r['zip_crc_pass']=r['zip_crc_first_bad_member'] is None
 out[arm]=r
 print(arm,json.dumps(dict(archive_bytes=r['bytes'],sha256=r['sha256'],members=len(r['members']),zip_crc_pass=r['zip_crc_pass'],event_counts=r['event_counts'],target_records=len(selected)),ensure_ascii=False),flush=True)
(ROOT/'evidence/PHASE0_LOCAL_ARCHIVE_AUDIT.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
for arm,r in out.items():
 with (ROOT/'evidence'/f'{arm}_TARGET_OBSERVER_RECORDS.jsonl').open('x',encoding='utf-8') as f:
  for d in r['target_records']:f.write(json.dumps(d,ensure_ascii=False)+'\n')
 with (ROOT/'evidence'/f'{arm}_RAW_MEMBER_CATALOG.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['name','bytes','compressed_bytes','crc32']);w.writeheader();w.writerows(r['members'])
print('seconds',time.monotonic()-t)
