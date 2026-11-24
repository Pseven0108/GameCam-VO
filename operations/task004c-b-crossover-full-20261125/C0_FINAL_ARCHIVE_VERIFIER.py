"""Verify existing streamed C0 TAR without downloading again or deserializing tensors."""
import pathlib,json,hashlib,tarfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\C0_IMMUTABLE_LOCAL_BACKUP.tar')
start=time.time();observed={};special={}
with tarfile.open(OUT,'r:') as tf:
 for m in tf:
  assert m.isfile() and m.name.startswith('C0/') and '..' not in pathlib.PurePosixPath(m.name).parts
  name=m.name[3:];assert name not in observed
  h=hashlib.sha256();n=0;chunks=[] if name in ('manifest.json','COMPLETE.json') else None
  with tf.extractfile(m) as f:
   for b in iter(lambda:f.read(8*1024**2),b''):
    h.update(b);n+=len(b)
    if chunks is not None:chunks.append(b)
  observed[name]={'sha256':h.hexdigest(),'bytes':n}
  if chunks is not None:special[name]=json.loads(b''.join(chunks))
m=special['manifest.json'];seal=special['COMPLETE.json']
assert m['state_sha256']=='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
assert observed['manifest.json']['sha256']==seal['manifest_sha256']
canonical=json.dumps({k:v for k,v in m.items() if k!='state_sha256'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
assert hashlib.sha256(canonical).hexdigest()==m['state_sha256']
assert set(observed)==set(m['files'])|{'manifest.json','COMPLETE.json'}
for n,v in m['files'].items():assert observed[n]=={'bytes':v['bytes'],'sha256':v['sha256']},n
h=hashlib.sha256()
with OUT.open('rb') as f:
 for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
r={'verification_start_unix':start,'verification_end_unix':time.time(),'CPU_only':True,'checkpoint_deserialized':False,'new_C0_captured':False,'remote_files_modified':False,'remote_temporary_archive_created':False,'archive_path':str(OUT),'archive_bytes':OUT.stat().st_size,'archive_sha256':h.hexdigest(),'archive_members':len(observed),'manifest_files_checked':len(m['files']),'all_member_SHA_match':True,'complete_seal_manifest_SHA_match':True,'canonical_object_graph_digest_match':True,'C0_state_sha256':m['state_sha256'],'original_C0_preserved':True,'second_download_performed':False,'verification_repair':'state_sha256 is canonical manifest object-graph digest, not a raw archive-member digest; verified using frozen control_common.canonical definition'}
(ROOT/'evidence/R3_C0_LOCAL_BACKUP_VERIFICATION.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
