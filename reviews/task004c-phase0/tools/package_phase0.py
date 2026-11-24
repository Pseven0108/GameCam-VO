import pathlib,json,zipfile,hashlib,os,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,d):
 with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
r=read(ROOT/'evidence/PHASE0_REMOTE.json');extra=read(ROOT/'evidence/PHASE0_EXTRA.json');v=read(ROOT/'evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json');final=read(ROOT/'evidence/FINAL_REMOTE_PRESERVATION.json')
public={k:r[k] for k in ['utc','hostname','gpu','gpu_processes','data','shm','source_git','source_status','files','manifest','python','cuda_versions','cgroup','seconds','checkpoint_inventory','inventory_errors','run_roots']}
public['omission_note']='Full raw stdout/proc args are retained locally and omitted from share package; no credential material is required for this audit.'
put(ROOT/'evidence/PHASE0_REMOTE_SHAREABLE.json',public)
put(ROOT/'evidence/NPZ_ARRAY_INVENTORY_AND_SOURCE_IDENTITY.json',{k:extra[k] for k in ['npz','original_git','original_status','source_verification','compiler','torch_build_static','legacy_npz']})
put(ROOT/'evidence/LOCAL_ARCHIVE_CHECKS_SHAREABLE.json',{a:{k:v[a][k] for k in ['archive','bytes','sha256','members','payload_checks','event_counts','event_keys','outer_identity_match','internal_sha256_matches','all_crc_pass']} for a in ['E0','E1']})
# Final state is a measured online GPU. Report here does not request or cause shutdown.
p=ROOT/'reports/FINAL_REVIEW.md';p.write_bytes((ROOT/'reports/TASK004C_FINAL_RESEARCH_REVIEW.md').read_bytes())
with (ROOT/'reports/EXECUTION_LOG.md').open('a',encoding='utf-8') as f:f.write('\n最终只读核验：8个目标历史数据文件SHA与归档完全一致；3090仍在线、空闲24125MiB、计算进程为空；远端可用字节未变。全部远端控制程序均为CPU标准库只读操作。\n')
# Declare exhaustive shareable payloads, excluding redundant exploratory artifacts and raw proc arguments.
payload={}
for folder in ['reports','results','tools','test_logs']:
 for p in sorted((ROOT/folder).rglob('*')):
  if p.is_file() and p.suffix!='.pyc':
   name=p.name if folder in ['reports','results'] else folder+'/'+p.relative_to(ROOT/folder).as_posix()
   assert name not in payload;payload[name]=p
for name in ['AUTHORIZATION_ORIGINAL.txt','AUTHORIZATION_GPU_PRIORITY.json']:
 payload[name]=ROOT/name
for name in ['HISTORICAL_IDENTITY_REFERENCE.json','PHASE0_REMOTE_PROCESS.json','PHASE0_EXTRA_PROCESS.json','PHASE0_REMOTE_SHAREABLE.json','NPZ_ARRAY_INVENTORY_AND_SOURCE_IDENTITY.json','LOCAL_ARCHIVE_CHECKS_SHAREABLE.json','HISTORICAL_RAW_ARCHIVE_VERIFICATION_SUMMARY.json','COMMON_INITIALIZATION_COMPARISON.json','METRIC3D_CACHE_RECOVERABILITY.json','LEGACY_BA278_REUSE_DECISION.json','FINAL_REMOTE_PRESERVATION.json','FINAL_REMOTE_PROCESS.json','SOURCE_EXCERPTS.txt','TASK004_OBSERVER_SOURCE_REFERENCE.py']:
 payload['evidence/'+name]=ROOT/'evidence'/name
for p in sorted((ROOT/'evidence/historical').rglob('*')):
 if p.is_file():payload['evidence/historical/'+p.relative_to(ROOT/'evidence/historical').as_posix()]=p
full=dict(payload)
full['evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json']=ROOT/'evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json'
full['evidence/HISTORICAL_BA_BOUNDARY_GRAPH.jsonl']=ROOT/'evidence/HISTORICAL_BA_BOUNDARY_GRAPH.jsonl'
checks=[]
for label,files,outname in [('light',payload,'GAMECAM_TASK004C_PHASE0_REVIEW_LIGHT_FOR_GPT.zip'),('full',full,'GAMECAM_TASK004C_PHASE0_CHECKPOINT_AUDIT_REVIEW.zip')]:
 man={n:dict(bytes=p.stat().st_size,sha256=sha(p)) for n,p in sorted(files.items())}
 encoded=json.dumps(dict(schema='GAMECAM_TASK004C_PACKAGE_SHA256_V1',payload=man,self_exclusion='FILE_SHA256_MANIFEST.json is excluded from recursive hashing; ZIP SHA256 is supplied outside.'),ensure_ascii=False,indent=2).encode()
 out=ROOT/outname
 with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,p in sorted(files.items()):z.write(p,n)
  z.writestr('FILE_SHA256_MANIFEST.json',encoded)
 with zipfile.ZipFile(out) as z:
  assert z.testzip() is None
  actual=read_manifest=json.loads(z.read('FILE_SHA256_MANIFEST.json'))['payload']
  assert set(z.namelist())==set(actual)|{'FILE_SHA256_MANIFEST.json'}
  for name,rec in actual.items():
   h=hashlib.sha256();length=0
   with z.open(name) as f:
    for chunk in iter(lambda:f.read(4*1024**2),b''):h.update(chunk);length+=len(chunk)
   assert h.hexdigest()==rec['sha256'] and length==rec['bytes'],name
 checksum=sha(out);check=dict(kind=label,file=str(out),bytes=out.stat().st_size,sha256=checksum,ZIP_CRC='PASS',payload_SHA256_matches=len(man),member_count=len(man)+1,A_executions=0,B_executions=0,GPU_online=True,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat());checks.append(check)
 with (ROOT/(outname+'.sha256')).open('x',encoding='ascii') as f:f.write(checksum+'  '+outname+'\n')
 # Save the manifest as a normal local delivery artifact too.
 with (ROOT/('FILE_SHA256_MANIFEST_'+label.upper()+'.json')).open('xb') as f:f.write(encoded)
put(ROOT/'PACKAGE_VALIDATION.json',dict(packages=checks,all_pass=True,scope='Phase0 evidence and missing-snapshot recovery proposal, not successful A/B research results',GPU_kept_online=True))
print(json.dumps(checks,ensure_ascii=False,indent=2))
