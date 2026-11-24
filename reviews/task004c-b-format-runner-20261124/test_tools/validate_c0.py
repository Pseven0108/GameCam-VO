import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,pathlib,time,shutil,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');p=r/'C0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
m=json.loads((p/'manifest.json').read_bytes());seal=json.loads((p/'COMPLETE.json').read_bytes())
assert sha(p/'manifest.json')==seal['manifest_sha256']
assert hashlib.sha256(canonical({k:v for k,v in m.items() if k!='state_sha256'})).hexdigest()==m['state_sha256']
assert {x.name for x in p.iterdir()}==set(m['files'])|{'manifest.json','COMPLETE.json'}
verified=[]
for name,row in m['files'].items():
 q=p/name;assert q.parent==p and not q.is_symlink() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256'],name
 verified.append({'file':name,**row})
prov=m['provenance'];assert prov['artifact_kind']=='NATIVE_C0' and prov['actual_boundary_rgb']==18
assert prov['candidate_source_commit']=='5d357c1d3079de134dd8b41a20a00632da37f0b0'
assert prov['candidate_source_tree']=='c018a65009aaf4f7457e2da5225a5f322a168b77'
assert prov['initialization_D']==0 and prov['W']==prov['U']==1 and prov['writer_barrier_and_closure_passed']
inv=prov['inventory'];assert len(inv['explicit_required_47_families'])==47
receipt=json.loads((r/'attempts/capture/PROCESS_RECEIPT.json').read_text());assert receipt['exit_code']==0 and receipt['success_receipt_exists']
captured=json.loads((r/'attempts/capture/C0_RECEIPT.json').read_text());assert captured['state_sha256']==m['state_sha256'] and captured['next_input_index']==18
budget=json.loads((r/'C0_EXACT_BUDGET_BEFORE_SAVE.json').read_text())
size=sum(x.stat().st_size for x in p.iterdir());assert size==budget['exact_checkpoint_logical_bytes']
status={'status':'PASS','time_unix':time.time(),'snapshot_kind':'NATIVE_C0','state_sha256':m['state_sha256'],
 'manifest_sha256':seal['manifest_sha256'],'storage_files_verified':len(verified),'snapshot_files':len(verified)+2,
 'actual_bytes':size,'uncompressed_storage_bytes':inv['storage_bytes'],'object_nodes':len(m['nodes']),
 'required_families':47,'next_input':prov['next_input'],'boundary':inv['C0_boundary_verified'],
 'source_commit':prov['candidate_source_commit'],'source_tree':prov['candidate_source_tree'],
 'data_disk_free_bytes':shutil.disk_usage(r).free,'process_receipt':receipt,
 'GPU_compute_apps':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],text=True),
 'files':verified}
with (r/'evidence/C0_POST_CAPTURE_INTEGRITY.json').open('x') as f:json.dump(status,f,indent=2)
print(json.dumps({k:v for k,v in status.items() if k!='files'}))
'''
out=call('C0_POST_CAPTURE_INTEGRITY_R1',code,timeout=180)
(ROOT/'evidence/C0_POST_CAPTURE_INTEGRITY_SUMMARY.json').write_text(out)
print(out)
