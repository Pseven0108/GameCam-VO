"""Final immutable asset verification and evidence-only collection."""
import base64,json,sys
from remote import ROOT,call
label=sys.argv[1] if len(sys.argv)>1 else '01'
code=r'''
import pathlib,json,hashlib,subprocess,shutil,os,base64,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');old=r.with_name('DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def git(p,*args):return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
release=json.loads((r/'evidence/CPU_STAGE_RELEASE.json').read_text())
checks={n:sha(r/n)==v for n,v in release['candidate_pins'].items()}
protected={n:sha(pathlib.Path(n))==v for n,v in release['protected_pins'].items()}
runtime={n:sha(pathlib.Path(n))==v for n,v in release['runtime_pins'].items()}
original={n:sha(old/n)==v for n,v in release['candidate_pins'].items()}
m=json.loads((r/'C0/manifest.json').read_text());oldm=json.loads((old/'C0/manifest.json').read_text());assert m==oldm
c0={n:sha(r/'C0'/n)==v['sha256'] and sha(old/'C0'/n)==v['sha256'] for n,v in m['files'].items()}
result={'unix':time.time(),'candidate_commit':git(r/'source_candidate','rev-parse','HEAD'),'candidate_tree':git(r/'source_candidate','rev-parse','HEAD^{tree}'),'candidate_clean':not git(r/'source_candidate','status','--porcelain','--untracked-files=all'),'original_source_clean':not git(old/'source_candidate','status','--porcelain','--untracked-files=all'),'candidate_files':len(checks),'candidate_all_match':all(checks.values()),'original_source_files':len(original),'original_source_all_match':all(original.values()),'protected_assets':len(protected),'protected_all_match':all(protected.values()),'runtime_assets':len(runtime),'runtime_all_match':all(runtime.values()),'C0_storage_files':len(c0),'C0_original_and_copy_all_match':all(c0.values()),'C0_state_sha256':m['state_sha256'],'free_disk_bytes':shutil.disk_usage(r).free,'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'instance_rebooted':False,'instance_shutdown':False,'new_C0_captures':0,'baseline_math_changed':False}
assert all(result[k] for k in ('candidate_clean','original_source_clean','candidate_all_match','original_source_all_match','protected_all_match','runtime_all_match','C0_original_and_copy_all_match'))
files={}
for rel in ('evidence','authorization','overlay','resource_monitor.py'):
 base=r/rel
 for p in ([base] if base.is_file() else base.rglob('*')):
  if p.is_file() and not p.is_symlink() and p.suffix not in ('.bin','.pt','.npz','.rrd'):
   files[p.relative_to(r).as_posix()]=base64.b64encode(p.read_bytes()).decode()
for rel in ('native_control/install.py','native_control/barrier.py','native_control/resource_check.py','src/depth_video.py','src/factor_graph.py','src/frontend.py','src/trajectory_filler.py','src/utils/eval_traj.py','task003_observer.py','runner/runtime_controls.py'):
 p=r/'source_candidate'/rel
 if p.is_file():files['additional_source_reference/'+rel]=base64.b64encode(p.read_bytes()).decode()
print(json.dumps({'files':files,'result':result,'protected_checks':protected,'runtime_checks':runtime}))
'''
a=call('R3_FINAL_IMMUTABLE_COLLECTION_'+label,code,timeout=480)
for rel,raw in a['files'].items():
 p=ROOT/'raw_evidence/R3_OFFLINE'/rel;p.parent.mkdir(parents=True,exist_ok=True)
 b=base64.b64decode(raw)
 if p.exists():assert p.read_bytes()==b,'Do not overwrite different evidence: '+str(p)
 else:p.write_bytes(b)
(ROOT/'evidence'/('R3_FINAL_IDENTITY_'+label+'.json')).write_text(json.dumps({k:v for k,v in a.items() if k!='files'},indent=2))
print(json.dumps({'collected_files':len(a['files']),**a['result']},indent=2))
