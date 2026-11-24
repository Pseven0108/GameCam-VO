"""Complete review publication with lossless chunked logs; assets remain private/local."""
import ast,difflib,gzip,hashlib,importlib.util,json,pathlib,re,zipfile
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
PUB=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\review_completed_20261125_R3')
import sys
sys.path.insert(0,str(ROOT/'tools'))
from evidence_locations import stage_dir,EXTERNAL_ROOT
CHUNK=32*1024**2
def source_name(src):
 try:return src.relative_to(ROOT).as_posix()
 except ValueError:return src.relative_to(EXTERNAL_ROOT).as_posix()
mapping=[];exclusions=[]
def sha_file(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def put(rel,text):
 p=PUB/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8',newline='\n')
def data(rel,x):put(rel,json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def clean(s):
 s=re.sub(r'(?:hz\d+|sc\d+)-ssh\.gpuhome\.cc(?::\d+)?','<REDACTED_SSH_HOST>',s)
 s=re.sub(r'jupyter-[A-Za-z0-9_-]+','<REDACTED_INSTANCE>',s)
 s=re.sub(r'SHA256:[A-Za-z0-9+/]{25,}={0,2}','<REDACTED_SSH_FINGERPRINT>',s)
 s=re.sub(r'("child_token"\s*:\s*")[^"]+("\s*[,}])',r'\1<REDACTED_RUN_TOKEN>\2',s)
 s=re.sub(r'(--ServerApp\.token=)[^\s"\\]+',r'\1<REDACTED>',s)
 s=re.sub(r'([?&]token=)[^\s"&\\]+',r'\1<REDACTED>',s)
 return s

def add(src,rel):
 reason=None
 if src.suffix in ('.rrd','.pt','.bin','.safetensors','.jpg','.jpeg','.gif','.pyc') or src.name.startswith('events.out.tfevents.'):
  reason='Large native recording, Tensor storage or RGB asset: retained locally with SHA/size'
 if src.suffix=='.png' and not rel.startswith('evaluation/'):reason='Potential RGB visualization retained locally'
 if src.name=='video.npz':reason='Native depth video contains input RGB: array inventory only, binary remains local'
 if reason:
  entry={'source':source_name(src),'sha256':sha_file(src),'bytes':src.stat().st_size,'reason':reason}
  if src.name=='video.npz':
   with np.load(src,allow_pickle=False) as z:
    entry['arrays']=[{'name':k,'shape':list(z[k].shape),'dtype':str(z[k].dtype),'bytes':z[k].nbytes,'raw_array_sha256':hashlib.sha256(z[k].tobytes()).hexdigest()} for k in z.files]
  exclusions.append(entry);return
 if src.suffix=='.jsonl' and src.stat().st_size>4*1024**2:
  rawhash=hashlib.sha256();pubhash=hashlib.sha256();chunks=[];size=0;part=None;current=0;changed=False
  with src.open('rb') as reader:
   for raw in reader:
    rawhash.update(raw);out=clean(raw.decode('utf-8')).encode('utf-8');pubhash.update(out);changed|=out!=raw
    if part is None or current>=CHUNK:
     if part:part.close()
     name=rel+'.part'+str(len(chunks)+1).zfill(3)+'.gz';p=PUB/name;p.parent.mkdir(parents=True,exist_ok=True)
     part=gzip.GzipFile(filename=str(p),mode='wb',compresslevel=6,mtime=0);chunks.append({'path':name,'uncompressed_bytes':0});current=0
    part.write(out);current+=len(out);size+=len(out);chunks[-1]['uncompressed_bytes']+=len(out)
   if part:part.close()
  for x in chunks:x['bytes']=(PUB/x['path']).stat().st_size;x['sha256']=sha_file(PUB/x['path'])
  info={'schema':'CONCATENATE_GZIP_CHUNKS_V1','original_source':source_name(src),'original_bytes':src.stat().st_size,'original_sha256':rawhash.hexdigest(),'public_log_bytes':size,'public_log_sha256':pubhash.hexdigest(),'sanitized':changed,'chunks':chunks,'reconstruction':'Concatenate gzip.decompress bytes in listed order. Public hash covers concatenated sanitized bytes; original hash authenticates retained canonical raw evidence.'}
  data(rel+'.chunks.json',info);mapping.append(info);return
 raw=src.read_bytes()
 try:out=clean(raw.decode('utf-8-sig')).encode('utf-8')
 except UnicodeDecodeError:out=raw
 p=PUB/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(out)
 mapping.append({'source':source_name(src),'public':rel,'raw_sha256':hashlib.sha256(raw).hexdigest(),'public_sha256':hashlib.sha256(out).hexdigest(),'sanitized':out!=raw})

def build():
 assert not PUB.exists();PUB.mkdir()
 audit=json.loads((ROOT/'evaluation/COMPLETED_STAGE_CONTROL_AUDIT.json').read_text());assert audit['formal_complete']==4 and not audit['missing']
 for sub in ('raw_evidence','overlay_r3','tests','source_reference','analysis','analysis_failures','evaluation','authorization'):
  for p in sorted((ROOT/sub).rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts:add(p,p.relative_to(ROOT).as_posix())
 for arm in ('B4','B3'):
  base=stage_dir(arm)
  if not base.is_relative_to(ROOT):
   for p in sorted(base.rglob('*')):
    if p.is_file():add(p,'raw_evidence/R3_OFFLINE/attempts/'+arm+'/'+p.relative_to(base).as_posix())
 for p in sorted((ROOT/'tools').glob('r3_*.py')):add(p,'tools/'+p.name)
 for name in ('build_completed_review_r3.py','publish_completed_review_r3.py'):
  add(ROOT/'tools'/name,'tools/'+name)
 add(ROOT/'tools/evidence_locations.py','tools/evidence_locations.py')
 for p in sorted((ROOT/'evidence').glob('*.json')):
  if p.name=='R3_SHUTDOWN_DOC_AUDIT.json':
   doc=json.loads(p.read_text(encoding='utf-8'));data('execution/R3_SHUTDOWN_DOCUMENT_REFERENCE.json',{k:doc[k] for k in ('url','HTTP_status','bytes','html_sha256','text_sha256') if k in doc});continue
  if p.name.startswith(('R3_','SERIAL_CONTINUATION_')):add(p,'execution/'+p.name)
 for p in sorted((ROOT/'evidence').glob('*CONTINUATION*.jsonl')):add(p,'execution/'+p.name)
 for p in sorted((ROOT/'evidence').glob('R3_FINAL_CPU_*.txt')):add(p,'execution/'+p.name)
 spec=importlib.util.spec_from_file_location('r3_review_overlay',ROOT/'overlay_r3/io_import_overlay.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 original=(ROOT/'source_reference/native_control/native_driver.py').read_bytes();effective=mod.transformed(original)
 put('overlay_r3/NATIVE_DRIVER_IO_ONLY.diff',''.join(difflib.unified_diff(original.decode().splitlines(True),effective.splitlines(True),fromfile='frozen/native_control/native_driver.py',tofile='in_memory/native_control/native_driver.py')))
 put('overlay_r3/EFFECTIVE_NATIVE_DRIVER.py',effective)
 identity=json.loads((ROOT/'evidence/R3_FINAL_IDENTITY_01.json').read_text());data('FINAL_ASSET_PRESERVATION.json',identity)
 for p in sorted((ROOT/'final_reports').glob('*.md')):add(p,p.name)
 data('STAGE_LEDGER.json',audit)
 data('SECURITY_AUDIT.json',{'gpu_used':True,'CUDA_context_initialized':True,'checkpoint_restored':True,'new_C0_capture':False,'DROID_W_executed':True,'DROID_SLAM_executed':False,'model_training':False,'baseline_math_modified':False,'frozen_source_files_modified':False,'R2_YAML_modified':False,'weights_modified':False,'CUDA_extensions_rebuilt':False,'GT_used_for_tracking':False,'GT_used_offline_scoring':True,'historical_results_deleted':False,'instance_shutdown':False,'shutdown_authorized_after_verified_publication':True,'shutdown_status_at_package_seal':'NOT_EXECUTED_YET_SEPARATE_RECEIPT_TO_FOLLOW','instance_rebooted':False,'formal_successful_arms':4,'failed_R2_B1_preserved':True,'short_successful_arms':4,'browser_rendering_verified':False,'native_Rerun_recordings_preserved':True})
 data('PUBLICATION_SANITIZATION_MAP.json',mapping);data('PUBLICATION_EXCLUSIONS.json',exclusions)
 # No transport transcripts or authentication helper are copied. Scan public text only.
 for p in PUB.rglob('*'):
  if not p.is_file() or p.suffix=='.gz':continue
  try:s=p.read_text(encoding='utf-8')
  except UnicodeDecodeError:continue
  assert not re.search(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',s),p
  assert not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})',s),p
  assert not re.search(r'(?:hz\d+|sc\d+)-ssh\.gpuhome\.cc',s),p
  assert not re.search(r'[?&]token=(?!<REDACTED>)[A-Za-z0-9_-]{10,}',s),p
 manifest={p.relative_to(PUB).as_posix():{'bytes':p.stat().st_size,'sha256':sha_file(p)} for p in sorted(PUB.rglob('*')) if p.is_file()}
 data('FILE_SHA256_MANIFEST.json',{'schema':'SHA256_V1','scope':'Every package file except this manifest; ZIP digest covers manifest','files':manifest})
 name='TASK004C_B_CROSSOVER_FULL_REVIEW_20261125.zip';zp=EXTERNAL_ROOT/name;assert not zp.exists()
 with zipfile.ZipFile(zp,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(PUB.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(PUB).as_posix(),compress_type=zipfile.ZIP_STORED if p.suffix=='.gz' else zipfile.ZIP_DEFLATED)
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None and set(z.namelist())==set(manifest)|{'FILE_SHA256_MANIFEST.json'}
  for n,v in manifest.items():
   h=hashlib.sha256();total=0
   with z.open(n) as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);total+=len(b)
   assert h.hexdigest()==v['sha256'] and total==v['bytes'],n
 report={'ZIP':name,'ZIP_path':str(zp),'ZIP_bytes':zp.stat().st_size,'ZIP_sha256':sha_file(zp),'ZIP_CRC':'PASS','manifest_files':len(manifest),'manifest_all_match':True,'members':len(manifest)+1,'expanded_review':str(PUB),'excluded_assets':len(exclusions),'largest_expanded_file_bytes':max(v['bytes'] for v in manifest.values())}
 (ROOT/'COMPLETED_PACKAGE_VALIDATION.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':build()
