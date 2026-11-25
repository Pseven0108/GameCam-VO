"""Full R2 review ZIP: all ten outputs, exact input archive, logs and observer binary."""
import os,sys,pathlib,json,hashlib,zipfile,tarfile,re,shutil,ast
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1')
DEST=ROOT/'07_release/review'
SECRET=re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|[?&]token=[A-Za-z0-9%_=-]{12,}|Authorization:\s*Bearer\s+[A-Za-z0-9_=-]{20,}',re.I)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def prove_zip(path):
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  m=json.loads(z.read('FILE_SHA256_MANIFEST.json'))['files']
  assert set(z.namelist())==set(m)|{'FILE_SHA256_MANIFEST.json'}
  for n,w in m.items():
   h=hashlib.sha256();size=0
   with z.open(n) as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);size+=len(b)
   assert size==w['bytes'] and h.hexdigest()==w['sha256'],n
  return len(m)
def main():
 assert not DEST.exists()
 decision=json.loads((ROOT/'R2_DECISION.json').read_text());assert decision['gpu_two_iteration_BA_calls']==10
 assert json.loads((ROOT/'03_tests/recorded/RECORDED_TESTS.json').read_text())['PASS']
 old=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1/07_release'
 oldproof=json.loads((old/'PACKAGE_VALIDATION.json').read_text());assert sha(old/oldproof['ZIP'])==oldproof['ZIP_sha256']
 DEST.mkdir()
 files=list(ROOT.glob('*.md'))+list(ROOT.glob('*.json'))
 for directory in ['00_intake','01_runtime','02_candidate','03_tests','04_analysis','05_reports','06_runtime_evidence']:
  for p in (ROOT/directory).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.so'] and not (directory=='00_intake' and p.name.endswith('.stderr.txt')):files.append(p)
 files+=[p for p in (ROOT/'07_release').glob('*.py')]
 for p in sorted(set(files)):
  dest=DEST/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 receipts=[{'file':p.name,**json.loads(p.read_text())} for p in sorted((ROOT/'00_intake').glob('*.receipt.json'))]
 (DEST/'00_intake/SSH_OPERATION_RECEIPTS.json').write_text(json.dumps({'receipts':receipts,'SSH_verbose_debug_local_only':True},indent=2)+'\n')
 excluded={'private_SSH_verbose_logs':'Kept locally; scientific process stdout/stderr fully included in 06_runtime_evidence and raw results.','prior_RESOURCE_PROBE_not_read_or_packaged':True,'credentials_in_package':False,'raw_RGB_dataset_GT_or_model_weights_in_package':False,'complete_single_BA_input_snapshot':'Included in full ZIP only; derived model features and estimated state, not raw images or model weights.'}
 (DEST/'PUBLICATION_EXCLUSIONS.json').write_text(json.dumps(excluded,indent=2)+'\n')
 binary=RECEIVER/'expanded/build/gamecam_task005b_r2_observer.so'
 assert sha(binary)=='6485409710451da8207154675ac7206f456ecb26bc4fc3baa82a6de12d1ea94c'
 raw={}
 for phase in ['plain','trace']:
  for p in (RECEIVER/'expanded/results'/phase).glob('*.npz'):raw['raw/results/'+phase+'/'+p.name]=p
 assert len(raw)==10
 snap=json.loads((ROOT/'00_intake/INPUT_SNAPSHOT_VERIFIED.json').read_text())
 p=pathlib.Path(snap['archive']);assert sha(p)==snap['archive_sha256']
 with tarfile.open(p) as t:
  for n,w in snap['members'].items():
   member=next(x for x in t.getmembers() if pathlib.PurePosixPath(x.name).name==n)
   h=hashlib.sha256()
   with t.extractfile(member) as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
   assert member.size==w['bytes'] and h.hexdigest()==w['sha256'],n
 raw['raw/input/snapshot_D0_S1_RGB233.tar']=p
 raw['raw/diagnostic_binary/gamecam_task005b_r2_observer.so']=binary
 rawindex={n:{'bytes':p.stat().st_size,'sha256':sha(p)} for n,p in raw.items()}
 (DEST/'COMPLETE_RAW_ASSET_INDEX.json').write_text(json.dumps({'all_assets_embedded_in_full_review_ZIP':True,'files':rawindex},indent=2)+'\n')
 bad=[];parsed=[]
 for p in DEST.rglob('*'):
  if not p.is_file():continue
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'));parsed.append(p.relative_to(DEST).as_posix())
  if p.suffix not in ['.npz','.png','.jpg','.so'] and SECRET.search(p.read_bytes()):bad.append(p.relative_to(DEST).as_posix())
 assert not bad,bad
 (DEST/'PACKAGE_CHECKS.json').write_text(json.dumps({'PASS':True,'python_AST_parsed':parsed,'secret_scan_PASS':True,'R1_review_ZIP_SHA_preserved':True,'input_archive_all_members_reverified':True,'ten_native_outputs_present':True},indent=2)+'\n')
 browse={p.relative_to(DEST).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.rglob('*')) if p.is_file()}
 (DEST/'FILE_SHA256_MANIFEST.json').write_text(json.dumps({'scope':'Browsable review tree; excludes this self-reference; large raw assets listed separately','files':browse},indent=2)+'\n')
 manifest={**browse,**rawindex}
 manifest['BROWSABLE_FILE_SHA256_MANIFEST.json']={'bytes':(DEST/'FILE_SHA256_MANIFEST.json').stat().st_size,'sha256':sha(DEST/'FILE_SHA256_MANIFEST.json')}
 target=ROOT/'07_release/GAMECAM_TASK005B_R2_REVIEW.zip'
 with zipfile.ZipFile(target,'x',allowZip64=True) as z:
  for n in browse:z.write(DEST/n,n,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
  z.write(DEST/'FILE_SHA256_MANIFEST.json','BROWSABLE_FILE_SHA256_MANIFEST.json',compress_type=zipfile.ZIP_DEFLATED)
  for n,p in raw.items():z.write(p,n,compress_type=zipfile.ZIP_STORED)
  z.writestr('FILE_SHA256_MANIFEST.json',json.dumps({'algorithm':'SHA256','scope':'All full ZIP members except this self-reference','files':manifest},indent=2)+'\n',compress_type=zipfile.ZIP_DEFLATED)
 count=prove_zip(target)
 proof={'PASS':True,'scientific_status':decision['status'],'ZIP':target.name,'ZIP_path':str(target),'ZIP_bytes':target.stat().st_size,'ZIP_sha256':sha(target),'ZIP_members':count+1,'manifest_items':count,'CRC':'PASS','all_member_SHA':'PASS','complete_raw_array_files':10,'complete_original_input_archive_included':True,'diagnostic_binary_included':True,'browse_directory':str(DEST),'browse_files':len(browse)+1,'R1_review_ZIP_preserved':True}
 (ROOT/'07_release/PACKAGE_VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
