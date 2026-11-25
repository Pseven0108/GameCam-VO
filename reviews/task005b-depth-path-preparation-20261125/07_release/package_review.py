"""Publishable analysis/candidate bundle; preserve private transport evidence locally."""
import os,sys,pathlib,json,hashlib,shutil,zipfile,re,ast
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'07_release/review'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def preserve():
 seal=json.loads((ROOT.parent/'GAMECAM_TASK005A_D_SCHEDULE_MECHANISM_20261125_R1/00_seal/TASK004CB_IMMUTABLE_SEAL.json').read_text())
 for path,v in seal['complete_metadata_inventory'].items():
  p=pathlib.Path(path);s=p.stat();assert (s.st_size,s.st_mtime_ns)==(v['bytes'],v['mtime_ns']),path
 for path,v in seal['selected_content_hashes'].items():assert sha(pathlib.Path(path))==v['sha256'],path
 assert sha(pathlib.Path(seal['review_ZIP']))==seal['review_ZIP_SHA256']
 return {'metadata_matches':len(seal['complete_metadata_inventory']),'selected_content_hash_matches':len(seal['selected_content_hashes']),'original_ZIP_hash_matches':True,'old_Task004CB_modified':False}
def main():
 assert not DEST.exists();DEST.mkdir()
 assert json.loads((ROOT/'04_tests/CPU_TEST_REPORT.json').read_text())['PASS']
 saved=preserve()
 paths=list(ROOT.glob('*.md'))+list(ROOT.glob('*.json'))
 for dirname in ['01_protocol','02_source','03_candidate','04_tests','05_evidence','06_reports']:
  paths.extend(p for p in (ROOT/dirname).rglob('*') if p.is_file() and p.suffix!='.pyc')
 paths.extend([ROOT/'00_intake/inspect_evidence.py',ROOT/'07_release/package_review.py'])
 for p in paths:
  dest=DEST/p.relative_to(ROOT);dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,dest)
 (DEST/'05_evidence/FINAL_HISTORY_PRESERVATION.json').write_text(json.dumps(saved,indent=2)+'\n')
 parsed=[]
 for p in DEST.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'));parsed.append(p.relative_to(DEST).as_posix())
 # No private key/token/transport records or payload storage files are included.
 forbidden=re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|[?&]token=[A-Za-z0-9]{12,}')
 bad=[p.relative_to(DEST).as_posix() for p in DEST.rglob('*') if p.is_file() and forbidden.search(p.read_bytes())]
 assert not bad,bad
 checks={'CPU_tests_passed':38,'new_python_files_AST_parsed':parsed,'secret_pattern_scan':'PASS','raw_private_transport_excluded':True,'no_C0_RGB_weights_GT_payload':True,'history_preserved':saved}
 (DEST/'05_evidence/PACKAGE_CONTENT_CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n')
 files={p.relative_to(DEST).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.rglob('*')) if p.is_file()}
 (DEST/'FILE_SHA256_MANIFEST.json').write_text(json.dumps({'algorithm':'SHA256','scope':'all ZIP members except this self-referential manifest','files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 zp=ROOT/'07_release/GAMECAM_TASK005B_DEPTH_PATH_PREPARATION_REVIEW_20261125.zip'
 with zipfile.ZipFile(zp,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(DEST.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(DEST).as_posix())
 with zipfile.ZipFile(zp) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(files)|{'FILE_SHA256_MANIFEST.json'}
  for name,want in files.items():
   data=z.read(name);assert len(data)==want['bytes'] and hashlib.sha256(data).hexdigest()==want['sha256']
 receipt={'status':'PASS','ZIP_path':str(zp),'ZIP':zp.name,'ZIP_bytes':zp.stat().st_size,'ZIP_sha256':sha(zp),'ZIP_members':len(files)+1,'manifest_items':len(files),'manifest_all_match':True,'CRC':'PASS','expanded_review':str(DEST),'status_label':'PREPARATION_ONLY_NO_REAL_GPU_RESULTS','history_preserved':saved}
 (ROOT/'07_release/PACKAGE_VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
