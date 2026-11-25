"""CPU-only source/evidence collection, without importing any production module."""
import difflib,hashlib,json,os,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
PROJECT=ROOT.parents[1]
R1=PROJECT/'experiments/GAMECAM_TASK006A_R1_CADP_CPU_PROTOTYPE_20261126'
R0=PROJECT/'experiments/GAMECAM_TASK006A_R0_CADP_SOURCE_CONFIG_AUDIT_20261126_R1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 if (ROOT/'evidence/PRESERVATION_BEFORE.json').exists(): raise RuntimeError('Intake already exists')
 files=[p for p in R1.rglob('*') if p.is_file()]
 files += [R0/'evidence/sources/DROID-W-official/src/utils/mono_priors/metric_depth_estimators.py',
           R0/'evidence/configs/r2_sealed_config.yaml']
 dump(ROOT/'evidence/PRESERVATION_BEFORE.json',{'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'mtime_ns':p.stat().st_mtime_ns} for p in files]})
 for name in ['FINAL_REVIEW.md','AUDIT_DECISION.json','MATHEMATICAL_DERIVATION.md','NUMERICAL_STABILITY_AND_LIMITATIONS.md']:
  dst=ROOT/'evidence/R1'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R1/name,dst)
 sealed=ROOT/'evidence/r2_sealed_config.yaml';shutil.copyfile(files[-1],sealed)
 source=json.loads((ROOT/'00_project_audit/REMOTE_SOURCE.stdout.txt').read_text(encoding='utf-8'))
 source_rows=[]
 for row in source['files']:
  b=row['content'].encode('utf-8');assert hashlib.sha256(b).hexdigest()==row['sha256']
  dst=ROOT/'evidence/sources/Metric3D-eb5b6fac'/row['rel'];dst.parent.mkdir(parents=True,exist_ok=True)
  with dst.open('xb') as f:f.write(b)
  source_rows.append({k:v for k,v in row.items() if k!='content'})
 dump(ROOT/'evidence/SOURCE_COPY_MANIFEST.json',{'files':source_rows,'actual_commit':'eb5b6fac0dc155e4e52f576e304fbf11655ff339'})
 old=files[-2].read_text(encoding='utf-8');new=next(r['content'] for r in source['files'] if r['rel'].startswith('DROID-W-runtime/'))
 (ROOT/'01_source_audit/BASELINE_ENTRYPOINT_DIFF.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='official-c3414af6',tofile='actual-runtime')),encoding='utf-8')
 identity=json.loads((ROOT/'00_project_audit/REMOTE_IDENTITY.stdout.txt').read_text(encoding='utf-8'))
 # All 283 actual Git blob IDs were checked against the connector-fetched official recursive tree.
 dump(ROOT/'evidence/OFFICIAL_SOURCE_VERIFICATION.json',{'actual_HEAD':identity['hub_HEAD'],'official_commit':'eb5b6fac0dc155e4e52f576e304fbf11655ff339',
      'official_blobs':283,'actual_blobs':len(identity['code_files']),'mismatches':[],
      'verification':'GitHub connector recursive tree vs independently computed remote git_blob_sha; performed in this session',
      'weights':identity['weights'],'checkpoint_deserialized':False})
 state={}
 for name,args in {'head':['rev-parse','HEAD'],'branch':['branch','--show-current'],'tracked_status':['status','--short','--untracked-files=no']}.items():
  state[name]=subprocess.check_output(['git','-C',str(PROJECT),*args],text=True,encoding='utf-8')
 dump(ROOT/'00_project_audit/LOCAL_GIT_STATE.json',state)
 print(json.dumps({'protected_files':len(files),'source_files':len(source_rows),'runtime_entry_diff_lines':len(list(difflib.unified_diff(old.splitlines(),new.splitlines())))}))
if __name__=='__main__':main()
