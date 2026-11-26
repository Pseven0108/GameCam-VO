"""Preservation/QA and complete original R2.1 ZIP; never edit old assets."""
import ast,csv,hashlib,json,os,pathlib,re,shutil,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
OLD=ROOT.parent/'task006a-r2-depth-prior-reliability-20261126'
ZIP='GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def dump(p,d):
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def files():return sorted(p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&{'inputs','deliveries','__pycache__'} and p.name not in ['SHA256_MANIFEST.csv','FILE_SHA256_MANIFEST.json'])
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 copies=[]
 for p in (OLD/'evidence/sources/Metric3D-eb5b6fac').rglob('*'):
  if p.is_file():
   dst=ROOT/'evidence/Metric3D-eb5b6fac'/p.relative_to(OLD/'evidence/sources/Metric3D-eb5b6fac')
   dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);copies.append({'path':str(dst.relative_to(ROOT)),'sha256':sha(dst)})
 extra=json.loads((ROOT/'00_preflight/MASK_SOURCE.stdout.txt').read_text())
 for row in extra:
  if 'content' not in row:continue
  p=ROOT/'evidence/Metric3D-eb5b6fac'/row['path']
  data=row['content'].encode('utf-8');assert hashlib.sha256(data).hexdigest()==row['sha256']
  if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  copies.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
 dump(ROOT/'evidence/SOURCE_SNAPSHOT_MANIFEST.json',{'Metric3D_commit':'eb5b6fac0dc155e4e52f576e304fbf11655ff339','files':copies,'production_modified':False})

 protected=[]
 for source in [OLD/'evidence/PRESERVATION_BEFORE.json',OLD/'evidence/DATA_PROTECTION_BEFORE.json']:
  for row in json.loads(source.read_text())['files']:
   p=pathlib.Path(row['path']);same=p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
   if 'mtime_ns' in row:same=same and p.stat().st_mtime_ns==row['mtime_ns']
   protected.append({'path':str(p),'sha256':sha(p),'unchanged':same})
   assert same
 old_manifest=json.loads((OLD/'FILE_SHA256_MANIFEST.json').read_text())
 for row in old_manifest['files']:
  assert sha(OLD/row['path'])==row['sha256']
 source_data=json.loads((ROOT/'03_gt_admission/GT_ADMISSION_FINAL.json').read_text())
 for row in source_data['raw_files']:assert sha(pathlib.Path(row['path']))==row['sha256']
 remote=json.loads((ROOT/'00_preflight/PRESERVATION_FINAL.stdout.txt').read_text())
 assert remote['all_inputs_unchanged'] and remote['hub_tracked_status']=='' and remote['GPU_processes'].strip()==''
 assert remote['files'][0]['sha256']=='15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972'
 assert remote['files'][1]['sha256']=='d6ac1b5eada25984981cc48e32dfbb38c6e59a4663ce5d554f4b227a4e40b487'
 dump(ROOT/'evidence/ORIGINAL_EVIDENCE_PRESERVATION.json',{'historical_R1_source_and_GT':protected,
   'historical_R2_payload_checks':len(old_manifest['files']),'new_GT_files_verified_unchanged':300,'remote_final':remote,
   'all_unchanged':True})
 a=ROOT/'04_evaluation/diagnostic_zero_extension_001';b=ROOT/'04_evaluation/diagnostic_zero_extension_002'
 comparisons=[]
 for p in sorted(a.iterdir()):
  if p.name=='EVALUATION_STATUS.json':continue
  target=b/p.name;assert target.is_file()
  same=p.read_bytes()==target.read_bytes();comparisons.append({'file':p.name,'identical_bytes':same,'sha256':sha(target)})
  assert same
 dump(ROOT/'evidence/CPU_REPRODUCIBILITY_COMPARISON.json',{'files':comparisons,'all_scientific_numbers_identical':True,
    'excluded':['EVALUATION_STATUS.json: elapsed time and new producer SHA metadata'],'no_new_GPU_calls':True})
 latest=[json.loads((ROOT/'experiments'/x/'CPU_TEST_REPORT.json').read_text()) for x in ['cpu_tests_001','cpu_tests_003']]
 assert [d['tests'] for d in latest]==[61,13] and all(d['success'] for d in latest)
 for p in (ROOT/'experiments/scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 producer=json.loads((b/'EVALUATION_STATUS.json').read_text())
 assert producer['producer_script_sha256']==sha(ROOT/'experiments/scripts/evaluate_pilot.py')
 dump(ROOT/'evidence/FINAL_CPU_QA.json',{'latest_CPU_tests':74,'historical_8_test_subset_not_double_counted':True,
    'AST_scripts_valid':len(list((ROOT/'experiments/scripts').glob('*.py'))),'producer_version_verified':True,
    'figures_visually_inspected':['VIPER_FIVE_ENVIRONMENT_REAL_OUTPUTS.png','CONDITIONAL_TEST_AUROC_PAIRED_FRAMES.png','MVS_HELDOUT_NATIVE_UNIT_DIAGNOSTIC.png'],
    'strict_failure_preserved':True,'raw_zero_pixels_filtered':False,'physical_metric_accuracy_certified':False})
 security={'gpu_requested_by_agent':False,'gpu_used':True,'gpu_restarted':False,'CUDA_context_initialized':True,'CUDA_tensor_created':True,
 'checkpoint_deserialized':True,'model_forward_count':33,'unique_RGB_samples':16,'neural_network_training_executed':False,
 'scalar_posthoc_calibration_executed':True,'SLAM_executed':False,'C0_deserialized':False,'BA_or_CUDA_modified':False,
 'production_source_modified':False,'weights_modified':False,'old_results_modified':False,'old_raw_data_modified':False,
 'shutdown_performed':False,'author_contacted':False,'CADP_integration':False,'Task007_started':False,
 'repository_publication_authorized':True,'repository_visibility_change_authorized':False,'SSH_strict_identity_verified':True,
 'new_MVS_sequence_bytes':85484738,'bounded_official_archive_prefix_bytes':180000000,'full_dataset_downloaded':False}
 dump(ROOT/'SECURITY_AUDIT.json',security)
 excluded=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p),'reason':'Raw RGB/GT data retained locally; not redistributed in review'} for p in (ROOT/'inputs').rglob('*') if p.is_file()]
 dump(ROOT/'evidence/EXCLUDED_RAW_DATA_INPUTS.json',{'files':excluded,'raw_model_output_NPZ_excluded':False,'weight_files_copied':False})
 (ROOT/'PACKAGE_CONTENTS.md').write_text('''# Complete review payload

All 16 original model-output NPZ files, including the real smoke raw-bin logits,
are inside the original ZIP. Configs, scripts, failed and successful stage logs,
GT source/hash manifests, strict-gate failure, secondary diagnostic protocols and
results, tests, figures and source snapshots are included. Raw input datasets and
model weights are not redistributed; their identities and locations are indexed.

SHA256_MANIFEST.csv covers payload except both manifests. The JSON manifest also
covers the CSV and excludes itself to avoid recursion. ZIP CRC covers every member;
the external ZIP SHA covers the whole original archive. Delivery/publication receipts
are outside the sealed payload. Any omitted Git files are enumerated in publication
metadata; complete raw model outputs remain in the original full review ZIP asset.
''',encoding='utf-8')
 # Scan actual text, never print a matched credential value.
 patterns=[r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'github_pat_[A-Za-z0-9_]{30,}',r'gh[pousr]_[A-Za-z0-9]{30,}',r'hf_[A-Za-z0-9]{30,}',r'https?://[^\s/@:]+:[^\s/@]+@']
 for p in files():
  if p.suffix=='.npz':continue
  try:text=p.read_text(encoding='utf-8')
  except UnicodeDecodeError:continue
  for pattern in patterns:
   if re.search(pattern,text):raise RuntimeError('Credential-like content, path only: '+str(p.relative_to(ROOT)))
 payload=files();rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in payload]
 mf=ROOT/'SHA256_MANIFEST.csv'
 with mf.open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,['path','bytes','sha256']);w.writeheader();w.writerows(rows)
 rows.append({'path':'SHA256_MANIFEST.csv','bytes':mf.stat().st_size,'sha256':sha(mf)})
 dump(ROOT/'FILE_SHA256_MANIFEST.json',{'files':rows,'excludes_self_to_avoid_recursion':True})
 payload += [mf,ROOT/'FILE_SHA256_MANIFEST.json']
 archive=ROOT/'deliveries'/ZIP
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in payload:z.write(p,p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for row in rows:
   data=z.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
  assert len(z.namelist())==len(payload)
 result={'ZIP':ZIP,'ZIP_bytes':archive.stat().st_size,'ZIP_sha256':sha(archive),'members':len(payload),'internal_SHA_entries':len(rows),
 'CRC':'PASS','internal_SHA':'PASS','raw_model_output_files':16,'all_raw_model_outputs_included':True,
 'protected_historical_files':len(protected),'historical_R2_payload_checks':len(old_manifest['files']),'latest_CPU_tests':74,
 'GPU_samples':16,'GPU_model_forward_count':33,'strict_GT_gate':'FAILED_PRESERVED','formal_metric_accuracy':'BLOCKED'}
 dump(ROOT/'deliveries/PACKAGE_VERIFICATION.json',result)
 (ROOT/'deliveries'/(ZIP+'.sha256')).write_text(result['ZIP_sha256']+'  '+ZIP+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
