"""Preservation, static QA and byte-exact R2 research packaging. CPU only."""
import ast,csv,hashlib,importlib.metadata,io,json,os,pathlib,platform,re,subprocess,zipfile
from datetime import datetime,timezone,timedelta
ROOT=pathlib.Path(__file__).resolve().parents[2]
ARCHIVE='GAMECAM_TASK006A_R2_DEPTH_PRIOR_RELIABILITY_REVIEW.zip'

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def dump(p,d):
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write(p,s):
 with p.open('x',encoding='utf-8') as f:f.write(s)
def rel(p):return p.relative_to(ROOT).as_posix()
def payload_files():
 return sorted(p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&{'deliveries','runtime_site','literature_cache','__pycache__'}
               and p.name not in {'SHA256_MANIFEST.csv','FILE_SHA256_MANIFEST.json'})

def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 assert not (ROOT/'deliveries'/ARCHIVE).exists()
 # Recheck all protected originals before sealing any preservation claims.
 checks={}
 for original,label in [('evidence/PRESERVATION_BEFORE.json','R1_and_source'),('evidence/DATA_PROTECTION_BEFORE.json','MVS_original_data')]:
  before=json.loads((ROOT/original).read_text(encoding='utf-8'))['files'];out=[]
  for row in before:
   p=pathlib.Path(row['path']);actual=sha(p)
   same=actual==row['sha256'] and p.stat().st_size==row['bytes']
   if 'mtime_ns' in row:same=same and p.stat().st_mtime_ns==row['mtime_ns']
   out.append({'path':str(p),'bytes':p.stat().st_size,'sha256':actual,'unchanged':same})
  assert all(r['unchanged'] for r in out)
  checks[label]={'checked':len(out),'all_unchanged':True,'files':out}
 # Two actual remote identity reads must match, without model deserialization.
 remote=json.loads((ROOT/'00_project_audit/REMOTE_FINAL_IDENTITY.stdout.txt').read_text())
 original=json.loads((ROOT/'evidence/OFFICIAL_SOURCE_VERIFICATION.json').read_text())
 assert remote['hub_HEAD']==original['actual_HEAD']
 assert remote['files'][0]['sha256']==original['weights'][0]['sha256']
 assert remote['files'][1]['sha256']=='d6ac1b5eada25984981cc48e32dfbb38c6e59a4663ce5d554f4b227a4e40b487'
 assert remote['checkpoint_deserialized'] is False and remote['remote_mutation'] is False
 checks['remote']={'files':remote['files'],'hub_HEAD':remote['hub_HEAD'],'all_unchanged':True,'read_only':True}
 project=ROOT.parents[1]
 gitbefore=json.loads((ROOT/'00_project_audit/LOCAL_GIT_STATE.json').read_text())
 gitafter={k:subprocess.check_output(['git','-C',str(project),*args],text=True,encoding='utf-8') for k,args in
           {'head':['rev-parse','HEAD'],'branch':['branch','--show-current'],'tracked_status':['status','--short','--untracked-files=no']}.items()}
 assert gitbefore==gitafter
 checks['root_git']={'same_HEAD_branch_and_tracked_status':True,'state':gitafter}
 dump(ROOT/'evidence/ORIGINAL_EVIDENCE_PRESERVATION.json',checks)

 env={'timestamp_Asia_Shanghai':datetime.now(timezone(timedelta(hours=8))).isoformat(),'local_python':platform.python_version(),
      'local_platform':platform.platform(),'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],
      'local_packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','Pillow','matplotlib']},
      'isolated_packages':{'OpenEXR':'3.3.3','pypdf':'5.9.0'},
      'GPU_runtime':'UNAVAILABLE_UNCONFIRMED','GPU_probe':remote['GPU_read_only'],
      'remote_free_data_bytes_at_final_probe':remote['free_data_bytes'],
      'native_inference':False,'torch_imported_for_model':False}
 dump(ROOT/'evidence/ENVIRONMENT.json',env)
 write(ROOT/'evidence/environment.txt',json.dumps(env,ensure_ascii=False,indent=2)+'\n')

 # AST compilation is syntax-only; never execute production or model imports.
 own=list(sorted((ROOT/'experiments/scripts').glob('*.py')))
 for p in own:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
 test=json.loads((ROOT/'experiments/unit_tests_002/CPU_TEST_REPORT.json').read_text())
 assert test['tests']==test['passed']==61 and test['success'] and all(x['status']=='PASS' for x in test['records'])
 stdout=(ROOT/'experiments/unit_tests_002/stdout.txt').read_text()
 assert 'Ran 61 tests' in stdout and stdout.rstrip().endswith('OK')
 # Explicitly reject fabricated metrics or numeric-distribution rows.
 numeric=list(csv.DictReader((ROOT/'01_source_audit/R2_01_CONFIDENCE_NUMERICAL_AUDIT.csv').open(encoding='utf-8')))
 for row in numeric:
  assert row['execution_status']=='NOT_EXECUTED_GPU_UNAVAILABLE'
  assert all(row[k]=='' for k in ['min','max','mean','median','standard_deviation','nan_count','inf_count'])
 fields=['04_native_confidence/R2_04_NATIVE_CONFIDENCE_METRICS.csv','05_tta/R2_05_TTA_METRICS.csv']
 for name in fields:
  assert all(row['value']=='' for row in csv.DictReader((ROOT/name).open(encoding='utf-8')))
 dump(ROOT/'evidence/FINAL_STATIC_QA.json',{'own_scripts_AST_valid':len(own),'CPU_test_suite':{'passed':61,'scope':test['scope']},
      'unmeasured_numeric_cells_empty':True,'prior_assets_unchanged':True,'raw_GT_files_unchanged':True,
      'no_confidence_accuracy_claim':True,'decision':'PARTIAL / NO-GO_INSUFFICIENT_EVIDENCE',
      'script_hashes':{rel(p):sha(p) for p in own}})

 # Do not republish paper full texts, isolated library binaries, or datasets.
 excluded=[]
 for folder,reason in [('experiments/runtime_site','Local third-party tool dependencies, reproducible from package versions'),
                       ('experiments/literature_cache','Third-party paper full text; source URL and PDF SHA preserved in reading receipt')]:
  for p in sorted((ROOT/folder).rglob('*')):
   if p.is_file():excluded.append({'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p),'reason':reason})
 dump(ROOT/'evidence/EXCLUDED_SUPPORT_ASSETS.json',{'files':excluded,'research_outputs_excluded':False,
       'raw_dataset_and_checkpoint_copied':False,'literature_receipts_retained':True})

 # Scan payload text without printing access-bearing values if a pattern hits.
 patterns={
  'private_key':r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
  'github_token':r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
  'huggingface_token':r'hf_[A-Za-z0-9]{30,}',
  'URL_password':r'https?://[^\s/@:]+:[^\s/@]+@',
  'access_URL':r'(?:[?&](?:token|access_token|api_key)=)[A-Za-z0-9_-]{12,}'}
 findings=[];scanned=0
 for p in payload_files():
  try:s=p.read_bytes().decode('utf-8')
  except UnicodeDecodeError:continue
  scanned+=1
  for name,pattern in patterns.items():
   if re.search(pattern,s):findings.append({'path':rel(p),'pattern':name})
 assert not findings,findings
 security={k:False for k in ['gpu_requested','gpu_used','gpu_restarted','cuda_context_initialized','cuda_tensor_created',
  'checkpoint_deserialized','model_forward_executed','training_executed','real_slam_executed','C0_deserialized',
  'production_source_modified','original_CUDA_modified','weights_modified','R1_assets_modified','raw_dataset_modified',
  'R1_geometry_used_as_GT','new_dataset_download_performed','author_contacted','repository_visibility_changed']}
 security.update({'SSH_host_key_strictly_verified':True,'isolated_dependency_install_only':True,
                  'network_used_for_source_literature_and_metadata':True,'research_stage_complete':False,
                  'review_publication_authorized':True,'GitHub_publication':'DELIVERY_STEP_AFTER_RESEARCH_SEAL',
                  'text_credential_scan':{'scanned':scanned,'findings':findings}})
 dump(ROOT/'SECURITY_AUDIT.json',security)
 write(ROOT/'PACKAGE_CONTENTS.md','''# Package scope and checksum convention

The original ZIP contains every relevant new R2 script, report, result CSV/JSON,
figure, selected source snapshot and raw execution receipt in this review payload.
No model weights or complete raw dataset is copied. The small RGB/GT audit figure
is explicitly a data-alignment exhibit, not a prediction result.

Local isolated runtime_site packages and literature_cache full-text copies are
not redistributed. EXCLUDED_SUPPORT_ASSETS.json lists their identity and reason;
paper URL/SHA receipts and package versions remain reproducible in the payload.
No completed model experiment output is omitted: there was no model inference.

SHA256_MANIFEST.csv covers all payload files except that CSV and the JSON manifest.
FILE_SHA256_MANIFEST.json covers those files plus the CSV. It excludes itself to
avoid a recursive checksum. ZIP CRC checks every archive member. The original ZIP
SHA is recorded separately in deliveries and at review_packages on GitHub.
Deliveries/readback receipts are external to the sealed payload, avoiding self-reference.
''')

 files=payload_files()
 rows=[{'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
 with (ROOT/'SHA256_MANIFEST.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
 p=ROOT/'SHA256_MANIFEST.csv'
 rows.append({'path':rel(p),'bytes':p.stat().st_size,'sha256':sha(p)})
 dump(ROOT/'FILE_SHA256_MANIFEST.json',{'files':rows,'scope':'All archive members except this self-referential manifest',
      'exclusions':['FILE_SHA256_MANIFEST.json'],'recursive_checksum_intentionally_avoided':True})
 files+= [p,ROOT/'FILE_SHA256_MANIFEST.json']
 archive=ROOT/'deliveries'/ARCHIVE
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files:z.write(p,rel(p))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  assert len(z.namelist())==len(files) and len(set(z.namelist()))==len(files)
  for row in rows:
   b=z.read(row['path']);assert len(b)==row['bytes'] and sha_bytes(b)==row['sha256']
  assert all(z.read(rel(p))==p.read_bytes() for p in files)
 checksum=sha(archive)
 write(ROOT/'deliveries'/(ARCHIVE+'.sha256'),checksum+'  '+ARCHIVE+'\n')
 result={'ZIP_file':str(archive),'ZIP_bytes':archive.stat().st_size,'ZIP_sha256':checksum,
 'ZIP_CRC':'PASS','members':len(files),'internal_SHA256_verified':len(rows),'file_bytes_match_expanded_payload':True,
 'R1_source_protection_checks':checks['R1_and_source']['checked'],'GT_protection_checks':checks['MVS_original_data']['checked'],
 'CPU_tests':61,'all_protected_originals_unchanged':True,'security_scan':'PASS','status':'PARTIAL_NOT_COMPLETE_R2'}
 dump(ROOT/'deliveries/PACKAGE_VERIFICATION.json',result)
 print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
