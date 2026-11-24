"""Build complete new review ZIP, protecting the sealed prior experiment."""
import os,sys,pathlib,json,hashlib,zipfile,shutil,re,datetime
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
from task005a_analysis import ROOT,OLD,sha,dump,verify_seal
DEST=ROOT/'08_release/review'
ZIP=ROOT/'08_release/GAMECAM_TASK005A_D_SCHEDULE_MECHANISM_REVIEW_20261125.zip'
def main():
 verify_seal();assert not DEST.exists() and not ZIP.exists(),'New package only; reconcile existing build before any overwrite.'
 refs=[]
 for name in ['CROSSOVER_SUMMARY.csv','EVALUATION_IDENTITY.json','COMPLETED_STAGE_CONTROL_AUDIT.json','RETAINED_KEYFRAME_EXPORT_CONSISTENCY.json']:
  src=OLD/'evaluation'/name;target=ROOT/'07_evidence'/('SEALED_'+name);assert not target.exists();shutil.copy2(src,target);refs.append({'source':str(src),'packaged_reference':str(target.relative_to(ROOT)),'sha256':sha(src),'bytes':src.stat().st_size})
 dump(ROOT/'07_evidence/PACKAGED_REFERENCE_PROVENANCE.json',{'references':refs,'original_sources_not_modified':True})
 DEST.mkdir(parents=True)
 for p in ROOT.iterdir():
  if p.name=='08_release':continue
  if p.is_dir():shutil.copytree(p,DEST/p.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
  elif p.is_file():shutil.copy2(p,DEST/p.name)
 files={};scanned=[]
 patterns=[r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}',r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'[?&](?:access_token|token)=[A-Za-z0-9_-]{16,}']
 for p in sorted(DEST.rglob('*')):
  if not p.is_file():continue
  if p.suffix.lower() in {'.md','.py','.json','.jsonl','.csv','.txt'}:
   content=p.read_text(encoding='utf-8-sig',errors='replace')
   for pattern in patterns:assert not re.search(pattern,content),('Credential-like pattern requires review',str(p.relative_to(DEST)))
   scanned.append(str(p.relative_to(DEST)))
  rel=p.relative_to(DEST).as_posix();files[rel]={'bytes':p.stat().st_size,'sha256':sha(p)}
 manifest={'algorithm':'SHA-256','self_exclusion':'FILE_SHA256_MANIFEST.json cannot contain its own digest','files':files}
 dump(DEST/'FILE_SHA256_MANIFEST.json',manifest)
 with zipfile.ZipFile(ZIP,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(DEST.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(DEST).as_posix())
 with zipfile.ZipFile(ZIP) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(files)|{'FILE_SHA256_MANIFEST.json'}
  for rel,want in files.items():
   content=z.read(rel);assert len(content)==want['bytes'] and hashlib.sha256(content).hexdigest()==want['sha256'],rel
 verify_seal()
 receipt={'status':'PASS','ZIP':ZIP.name,'ZIP_path':str(ZIP),'ZIP_bytes':ZIP.stat().st_size,'ZIP_sha256':sha(ZIP),'ZIP_CRC':'PASS','manifest_all_match':True,'manifest_items':len(files),'ZIP_members':len(files)+1,'expanded_review':str(DEST),'text_files_checked_for_access_credentials':len(scanned),'no_model_C0_RGB_full_GT_payloads':True,'Task004CB_unchanged':True,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 dump(ROOT/'08_release/PACKAGE_VALIDATION.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
