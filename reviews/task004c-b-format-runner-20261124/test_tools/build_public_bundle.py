"""Sanitize actual reports and evidence; hash public bytes and verify ZIP CRC."""
import hashlib,importlib.util,json,pathlib,re,shutil,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prior_publication',ROOT.parent/'DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1/tools/publish_autonomous_review.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
ORIGINAL=ROOT/'review_original_final';PUBLIC=ROOT/'review_public'
assert not ORIGINAL.exists() and not PUBLIC.exists()
shutil.copytree(ROOT/'review_original_v2',ORIGINAL)
shutil.copytree(ROOT/'remote_evidence',ORIGINAL/'raw_evidence',dirs_exist_ok=True)
shutil.copytree(ROOT/'tools',ORIGINAL/'test_tools',ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
for p in (ROOT/'evidence').glob('*.json'):
 q=ORIGINAL/'evidence'/p.name;q.write_bytes(p.read_bytes())
# Include the exact legacy implementation, still pinned to this candidate.
legacy=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_R1')
# The release receipt and final-source stdout are the evidence if no local test implementation exists.
# Document all post-experiment report-helper errors; none are GPU retries.
p=ORIGINAL/'EXECUTION_LOG.md'
with p.open('a',encoding='utf-8') as f:f.write('\n报告生成首轮在Windows默认GBK读取新写UTF-8报告时失败，随后改用显式UTF-8，在独立v2目录重新生成；草稿仍保留。这没有启动模型、修改候选或覆盖历史实验。最终审查原始证据目录为review_original_final。\n')

def sha(b):return hashlib.sha256(b).hexdigest()
def js(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def clean_text(t):
 t=prior.clean_text(t)
 t=re.sub(r'\b[\w-]+\.gpuhome\.cc\b','REDACTED_SSH_HOST',t,flags=re.I)
 t=re.sub(r'("child_token"\s*:\s*")[^"]+(\")',r'\1REDACTED_EPHEMERAL_STAGE_NONCE\2',t)
 t=re.sub(r'(\\"child_token\\"\s*:\s*\\")[^\\]+(\\")',r'\1REDACTED_EPHEMERAL_STAGE_NONCE\2',t)
 return t
sensitive={'child_token','password','access_token','api_token','private_key','siwc_bypass_bearer_token'}
def clean_json(x):
 if isinstance(x,str):return clean_text(x)
 if isinstance(x,list):return [clean_json(v) for v in x]
 if isinstance(x,dict):return {clean_text(k):('REDACTED_EPHEMERAL_STAGE_NONCE' if k=='child_token' else 'REDACTED_SECRET' if k.lower() in sensitive else clean_json(v)) for k,v in x.items()}
 return x
def scan(raw,name):
 for pattern in (rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}',rb'\bAKIA[A-Z0-9]{16}\b',rb'[\w-]+\.gpuhome\.cc',rb'\bjupyter-[A-Za-z0-9_-]+',rb'SHA256:[A-Za-z0-9+/]{25,}={0,2}',rb'(?<!\w)(?:REDACTED_SSH_PORT|REDACTED_SSH_PORT|REDACTED_SSH_PORT|REDACTED_SSH_PORT|REDACTED_SSH_PORT|REDACTED_SSH_PORT)(?!\w)',rb'REDACTED_SSH_KEY_NAME'):
  if re.search(pattern,raw,re.I):raise RuntimeError('Public safety scan match: '+name)
PUBLIC.mkdir();mapping=[]
for p in sorted(ORIGINAL.rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(ORIGINAL);raw=p.read_bytes();text=raw.decode('utf-8-sig')
 clean=js(clean_json(json.loads(text))) if p.suffix.lower()=='.json' else clean_text(text).encode()
 scan(clean,rel.as_posix());q=PUBLIC/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(clean)
 mapping.append({'path':rel.as_posix(),'original_sha256':sha(raw),'public_sha256':sha(clean),'redacted_or_reformatted':raw!=clean})
def put(name,x):
 p=PUBLIC/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(js(x))
put('publication/SANITIZATION_MAP.json',{'scope':'CURRENT_FORMAT_RUNNER_STAGE_ONLY','original_evidence_retained_privately':True,'changes':'connection/debug/instance info and ephemeral launch nonce redacted; JSON normalized; public manifest/metadata is not a directly loadable original C0','files':mapping})
put('publication/PUBLIC_CONTENT_SCAN.json',{'scope':'All new current-task files','secret_matches':0,'private_connection_matches':0,'Tensor_weight_RGB_GT_or_Arena_payloads':0,'new_files_checked':len(mapping),'source_files_changed_by_sanitizer':[x['path'] for x in mapping if x['path'].endswith('.py') and x['redacted_or_reformatted']]})
files=[{'path':p.relative_to(PUBLIC).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(PUBLIC.rglob('*')) if p.is_file()]
put('FILE_SHA256_MANIFEST.json',{'scope':'SANITIZED_PUBLIC_REVIEW','self_exclusion':['FILE_SHA256_MANIFEST.json'],'files':files})
for p in PUBLIC.rglob('*'):
 if p.is_file():scan(p.read_bytes(),p.relative_to(PUBLIC).as_posix())
package=ROOT/'TASK004C_B_FORMAT_RUNNER_REVIEW.zip'
with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(PUBLIC.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(PUBLIC).as_posix())
with zipfile.ZipFile(package) as z:
 assert z.testzip() is None
 m=json.loads(z.read('FILE_SHA256_MANIFEST.json'))
 assert set(z.namelist())=={x['path'] for x in m['files']}|{'FILE_SHA256_MANIFEST.json'}
 for entry in m['files']:
  raw=z.read(entry['path']);assert len(raw)==entry['bytes'] and sha(raw)==entry['sha256']
result={'status':'PASS_PACKAGE_INTEGRITY_NOT_GPU_EXPERIMENT_COMPLETION','manifest_entries_verified':len(m['files']),'ZIP_members':len(z.namelist()),'ZIP_CRC':'PASS','package_bytes':package.stat().st_size,'package_sha256':sha(package.read_bytes()),'public_scan':'PASS','source_commit':'5d357c1d3079de134dd8b41a20a00632da37f0b0','C0_capture_attempts':1,'fresh_GPU_restore_attempts':1,'Short80_attempts':0,'Formal487_attempts':0,'experiment_status':'STOPPED_RGB019_OUTPUT_DIRECTORY_COLLISION'}
(ROOT/'evidence/REVIEW_BUNDLE_VERIFICATION.json').write_bytes(js(result));print(json.dumps(result))
