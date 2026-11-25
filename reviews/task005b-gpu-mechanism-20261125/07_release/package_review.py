"""Build a review ZIP plus explicit separate large-native-evidence index."""
import pathlib,sys,json,hashlib,zipfile,tarfile,re,shutil,ast,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
DEST=ROOT/'07_release/review'
prior_spec=importlib.util.spec_from_file_location('historical_preparation_packaging',r'D:\aaa\GameCam-VO\experiments\GAMECAM_TASK005B_DEPTH_PATH_DECOMPOSITION_20261125_R1\07_release\package_review.py')
prior_module=importlib.util.module_from_spec(prior_spec);prior_spec.loader.exec_module(prior_module)
preserve_prior=prior_module.preserve

def sha(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()

SECRET=re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|[?&]token=[A-Za-z0-9%_=-]{12,}|Authorization:\s*Bearer\s+[A-Za-z0-9_=-]{20,}',re.I)

def scan_raw(path):
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name.endswith('.npz'):continue
            with archive.extractfile(member) as stream:
                carry=b''
                for block in iter(lambda:stream.read(1024**2),b''):
                    data=carry+block
                    if SECRET.search(data):raise RuntimeError('Credential-like content in raw evidence: '+member.name)
                    carry=data[-512:]

def main():
    assert not DEST.exists()
    decision=json.loads((ROOT/'TASK005B_DECISION.json').read_text())
    assert decision['status']=='STOPPED_ENDPOINT_EQUIVALENCE_FAILURE'
    assert decision['native_calls_executed']==58 and decision['native_call_budget']==144
    assert decision['endpoint_checks_passed']==19 and decision['endpoint_checks_failed']==1
    assert not (ROOT/'04_results/SUPERVISOR_SUCCESS.json').exists()
    for name in ('ANALYSIS_UNIT_TESTS.json','NATIVE_ALGEBRA_UNIT_TESTS.json','LOCAL_AST_TEST.json'):
        assert json.loads((ROOT/'03_tests'/name).read_text())['PASS']
    preserved=preserve_prior()
    transfer=json.loads((ROOT/'07_release/RUN_EVIDENCE_TRANSFER.json').read_text())
    scan_raw(transfer['archive'])
    DEST.mkdir()
    files=list(ROOT.glob('*.md'))+list(ROOT.glob('*.json'))
    for subdir in ('01_runtime','02_candidate','03_tests','04_results','05_analysis','06_reports'):
        for p in (ROOT/subdir).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.lock') and p.name!='write_final_reports.py':
                files.append(p)
    files.extend([ROOT/'00_intake/AUTHORIZATION.json',ROOT/'07_release/RAW_ASSET_INDEX.json',ROOT/'07_release/RUN_EVIDENCE_TRANSFER.json',pathlib.Path(__file__)])
    files.append(ROOT/'00_intake/FROZEN_IDENTITY_AFTER_STOP_PUBLIC.json')
    for p in (ROOT/'07_release').glob('*.py'):
        if p not in files:files.append(p)
    for path in files:
        target=DEST/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    intake=[]
    for path in sorted((ROOT/'00_intake').glob('*receipt.json'))+sorted((ROOT/'00_intake').glob('*RECEIPT.json')):
        data=json.loads(path.read_text(encoding='utf-8-sig'));intake.append({'source_receipt':path.name,**data})
    (DEST/'00_intake/SSH_TRUST_AND_OPERATION_RECEIPTS.json').write_text(json.dumps(intake,indent=2))
    proof_index=[]
    for path in sorted(RECEIVER.glob('*.VERIFIED.json')):
        data=json.loads(path.read_text());proof_index.append(data)
    (DEST/'00_intake/LOCAL_IMMUTABLE_ARCHIVE_INDEX.json').write_text(json.dumps({'archives':proof_index,'retirement_receipts_supersede_source_removed_false_at_transfer_time':True},indent=2))
    (DEST/'00_intake/HISTORICAL_PRESERVATION.json').write_text(json.dumps(preserved,indent=2))
    (DEST/'00_intake/PUBLICATION_EXCLUSIONS.json').write_text(json.dumps({'raw_private_SSH_debug_not_included':True,'RESOURCE_PROBE_stdout_excluded_due_to_access_bearing_process_arguments':True,'RGB_GT_weights_C0_full_snapshot_payloads_excluded':True,'complete_native_arrays_separate_release_assets':'07_release/RAW_ASSET_INDEX.json'},indent=2))
    parsed=[]
    for path in DEST.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'));parsed.append(path.relative_to(DEST).as_posix())
    bad=[]
    for path in DEST.rglob('*'):
        if path.is_file() and path.suffix not in ('.npz','.png','.jpg','.pdf') and SECRET.search(path.read_bytes()):bad.append(path.relative_to(DEST).as_posix())
    assert not bad,bad
    (DEST/'00_intake/PACKAGE_CHECKS.json').write_text(json.dumps({'PASS':True,'python_AST_parsed':parsed,'secret_scan':'PASS','raw_log_decompressed_secret_scan':'PASS','history_preserved':preserved},indent=2))
    manifest={p.relative_to(DEST).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(DEST.rglob('*')) if p.is_file()}
    (DEST/'FILE_SHA256_MANIFEST.json').write_text(json.dumps({'algorithm':'SHA256','scope':'All ZIP members except this self-referential manifest','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    target=ROOT/'07_release/GAMECAM_TASK005B_GPU_MECHANISM_REVIEW_20261125.zip'
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(DEST).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())==set(manifest)|{'FILE_SHA256_MANIFEST.json'}
        for name,want in manifest.items():
            data=archive.read(name);assert len(data)==want['bytes'] and hashlib.sha256(data).hexdigest()==want['sha256']
    asset_count=len(json.loads((ROOT/'07_release/RAW_ASSET_INDEX.json').read_text())['assets'])
    proof={'status':'PASS','scientific_status':decision['status'],'ZIP_path':str(target),'ZIP':target.name,'ZIP_bytes':target.stat().st_size,'ZIP_sha256':sha(target),'ZIP_members':len(manifest)+1,'manifest_items':len(manifest),'CRC':'PASS','expanded_review':str(DEST),'separate_raw_assets':asset_count,'historical_preservation':preserved}
    (ROOT/'07_release/PACKAGE_VALIDATION.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof))

if __name__=='__main__':main()
