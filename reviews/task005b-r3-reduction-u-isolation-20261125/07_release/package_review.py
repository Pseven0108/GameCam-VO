"""Self-contained R3 review: original input, sealed R2 context and all 52 outputs."""
import os,sys,pathlib,json,hashlib,zipfile,tarfile,re,shutil,ast
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R3-20261125-R1')
R2=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
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
        for name,w in m.items():
            h=hashlib.sha256();size=0
            with z.open(name) as f:
                for b in iter(lambda:f.read(8*1024**2),b''):h.update(b);size+=len(b)
            assert size==w['bytes'] and h.hexdigest()==w['sha256'],name
        return len(m)
def main():
    assert not DEST.exists()
    decision=json.loads((ROOT/'R3_DECISION.json').read_text());assert decision['two_iteration_BA_calls']==20
    assert json.loads((ROOT/'03_tests/FULL_CPU_TEST_REPORT.json').read_text())['PASS']
    assert json.loads((ROOT/'ORIGINAL_EVIDENCE_PRESERVATION.json').read_text())['all_protected_SHA_unchanged']
    r2proof=json.loads((R2/'07_release/PACKAGE_VALIDATION.json').read_text());assert sha(r2proof['ZIP_path'])==r2proof['ZIP_sha256']
    DEST.mkdir();files=list(ROOT.glob('*.md'))+list(ROOT.glob('*.json'))
    for name in ['00_intake','01_runtime','02_candidate','03_tests','04_analysis','05_reports','06_runtime_evidence']:
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.so'] and not (name=='00_intake' and p.name.endswith('.stderr.txt')):files.append(p)
    files += list((ROOT/'07_release').glob('*.py'))
    for p in sorted(set(files)):
        dest=DEST/p.relative_to(ROOT);dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,dest)
    # Scientific process stdout/stderr included in full and expanded evidence.
    for p in (RECEIVER/'expanded/evidence').rglob('*'):
        if p.is_file():
            dest=DEST/'06_runtime_evidence'/p.relative_to(RECEIVER/'expanded/evidence');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for p in (RECEIVER/'expanded/results').glob('*.json'):
        dest=DEST/'06_runtime_evidence/result_receipts'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for name in ['BUILD_COMPLETE.json','build.ninja']:
        dest=DEST/'06_runtime_evidence/build'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(RECEIVER/'expanded/build'/name,dest)
    raw={'raw/results/'+p.name:p for p in (RECEIVER/'expanded/results').glob('*.npz')};assert len(raw)==52
    raw['raw/diagnostic_binary/gamecam_task005b_r3_isolation.so']=RECEIVER/'expanded/build/gamecam_task005b_r3_isolation.so'
    snap=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1/snapshot_D0_S1_RGB233.tar')
    assert sha(snap)=='906ee063eb919d6ccc70c28fa01d5542f96ac0692f63873582c3ef8950b19891'
    raw['raw/input/snapshot_D0_S1_RGB233.tar']=snap
    context=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1/expanded/results/trace/trace_reference_1.npz')
    assert sha(context)=='05425393e11cfb025a2b2e95234809e1f4b11ef39e29fe658d8f1912bf64b7b5'
    raw['raw/input/R2_trace_reference_1.npz']=context
    # Include all small R2 source functions used to generate the isolated copies.
    for p in [R2/'02_candidate/task005b_r2_kernels.cu',ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1/02_candidate/task005b_kernels.cu']:
        dest=DEST/'02_candidate/historical_sources'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for name in ['feedback_math.py','analyze_pairs.py']:
        dest=DEST/'04_analysis/historical_R2_dependencies'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R2/'04_analysis'/name,dest)
    rawindex={name:{'bytes':p.stat().st_size,'sha256':sha(p)} for name,p in raw.items()}
    (DEST/'COMPLETE_RAW_ASSET_INDEX.json').write_text(json.dumps({'all_assets_in_complete_ZIP':True,'files':rawindex},indent=2)+'\n')
    (DEST/'PUBLICATION_EXCLUSIONS.json').write_text(json.dumps({'SSH_verbose_logs_local_only':True,'scientific_stdout_stderr_complete':True,'raw_RGB_GT_model_weights_or_credentials_included':False,'historical_secret_bearing_RESOURCE_PROBE_read_or_packaged':False,'exact_BA_input_and_R2_intermediate_in_full_ZIP':True},indent=2)+'\n')
    bad=[];parsed=[]
    for p in DEST.rglob('*'):
        if not p.is_file():continue
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'));parsed.append(p.relative_to(DEST).as_posix())
        if p.suffix not in ['.npz','.png','.jpg','.so'] and SECRET.search(p.read_bytes()):bad.append(p.relative_to(DEST).as_posix())
    assert not bad,bad
    (DEST/'PACKAGE_CHECKS.json').write_text(json.dumps({'PASS':True,'AST_parsed_python_files':parsed,'secret_scan_PASS':True,'original_R2_review_ZIP_preserved':True,'all_52_native_outputs_present':True},indent=2)+'\n')
    browse={p.relative_to(DEST).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.rglob('*')) if p.is_file()}
    (DEST/'FILE_SHA256_MANIFEST.json').write_text(json.dumps({'scope':'All browsable files except this self-reference; large raw assets indexed separately','files':browse},indent=2)+'\n')
    manifest={**browse,**rawindex,'BROWSABLE_FILE_SHA256_MANIFEST.json':{'bytes':(DEST/'FILE_SHA256_MANIFEST.json').stat().st_size,'sha256':sha(DEST/'FILE_SHA256_MANIFEST.json')}}
    target=ROOT/'07_release/GAMECAM_TASK005B_R3_REVIEW.zip'
    with zipfile.ZipFile(target,'x',allowZip64=True) as z:
        for name in browse:z.write(DEST/name,name,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        z.write(DEST/'FILE_SHA256_MANIFEST.json','BROWSABLE_FILE_SHA256_MANIFEST.json',compress_type=zipfile.ZIP_DEFLATED)
        for name,p in raw.items():z.write(p,name,compress_type=zipfile.ZIP_STORED)
        z.writestr('FILE_SHA256_MANIFEST.json',json.dumps({'algorithm':'SHA256','scope':'All members except this self-reference','files':manifest},indent=2)+'\n',compress_type=zipfile.ZIP_DEFLATED)
    n=prove_zip(target)
    proof={'PASS':True,'scientific_status':decision['status'],'ZIP':target.name,'ZIP_path':str(target),'ZIP_bytes':target.stat().st_size,'ZIP_sha256':sha(target),'ZIP_members':n+1,'manifest_items':n,'CRC':'PASS','all_member_SHA':'PASS','complete_raw_output_files':52,'complete_original_input_archive_included':True,'sealed_R2_intermediate_included':True,'diagnostic_binary_included':True,'browse_directory':str(DEST),'browse_files':len(browse)+1}
    (ROOT/'07_release/PACKAGE_VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
