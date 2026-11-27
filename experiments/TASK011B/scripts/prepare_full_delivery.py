"""Build a reviewed explicit publication allowlist and complete original ZIP.

No automatic Git push occurs here. Credentials and raw datasets never enter the
allowlist. Every path is checked before Git or ZIP packaging.
"""
import csv,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
from common import ROOT,TASK,csvwrite,dump,sha

RELPATH='reviews/task011b-validity-aware-cadp-dr-20261127'
REVIEW=ROOT/RELPATH
PRIVATE=TASK/'private/publication'
ARCHIVE=ROOT/'review_packages/GAMECAM_TASK011B_VALIDITY_AWARE_CADP_DR_REVIEW.zip'
CODE_DIRS=('scripts','gpu','tests','CADP_DR_EXPERIMENTAL_BRANCH','CADP_DR_CONFIGS','CADP_DR_UNIT_TESTS','configs')


def acceptable(path):
    if '__pycache__' in path.parts or path.suffix.lower() in ('.pyc','.so','.dll','.exe','.whl','.pth','.pt','.safetensors','.ckpt','.jpg','.jpeg','.exr'):
        return False
    return True


def copy(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)


def stage_sources():
    upstream=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
    frozen='c3414af6047d06bafc1a6645d09f23247f3b2cdc'
    license_raw=subprocess.check_output(['git','-C',str(upstream),'show',frozen+':LICENSE'])
    license_path=REVIEW/'reproducibility/UPSTREAM_LICENSES/DROID-W-LICENSE.txt'
    license_path.parent.mkdir(parents=True,exist_ok=True);license_path.write_bytes(license_raw)
    (license_path.parent/'ATTRIBUTION.md').write_text(
        '# Candidate-source attribution\n\nThe task-local native candidate contains and modifies code from '
        'MoyangLi00/DROID-W, frozen commit '+frozen+'. The original LICENSE is preserved here. '
        'Candidate modifications, unchanged kernel bodies and upstream file identities are described in '
        '03_R2_CADP_DR_INTEGRATION and the source provenance/patch. Original upstream and existing '
        'third-party notices in source files remain intact.\n',encoding='utf-8')
    for folder in CODE_DIRS:
        for source in sorted((TASK/folder).rglob('*')):
            if source.is_file() and acceptable(source):
                copy(source,REVIEW/'reproducibility/experiments/TASK011B'/source.relative_to(TASK))
    # Refresh the review's convenient source mirror too; its initial metadata
    # was copied before actual native regression and must not claim no GPU run.
    for source in sorted((TASK/'CADP_DR_EXPERIMENTAL_BRANCH').rglob('*')):
        if source.is_file() and acceptable(source):
            copy(source,REVIEW/'03_R2_CADP_DR_INTEGRATION/CADP_DR_EXPERIMENTAL_BRANCH'/source.relative_to(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'))
    copy(TASK/'intake/NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json',
         REVIEW/'03_R2_CADP_DR_INTEGRATION/CADP_DR_EXPERIMENTAL_BRANCH/intake/NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json')
    # Exact scoring implementation and its actual helper, not a rewritten metric.
    pipe=Path('D:/aaa/GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/pipeline')
    for name in ('offline_eval.py','fullseq_common.py'):
        copy(pipe/name,REVIEW/'reproducibility/frozen_viper_metrics'/name)
    for name in ('reliability_metrics_frozen.py','TASK011B_AUTHORIZATION.txt','ORIGINAL_WEIGHT_PROTECTION.json',
                 'FINAL_ORIGINAL_ASSET_PROTECTION.json','GPU_PREFLIGHT_002.json','NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json',
                 'FORMAL_SOURCE_BLOB_AUDIT.json','FORMAL_SOURCE_LINE_ENDING_AUDIT.json',
                 'CANDIDATE_BINARY_MIDBATCH_IDENTITY.json'):
        copy(TASK/'intake'/name,REVIEW/'09_LOGS'/name)
        copy(TASK/'intake'/name,REVIEW/'reproducibility/experiments/TASK011B/intake'/name)
    for name in ('CPU_TESTS_005.log','CPU_TESTS_006.log','CPU_TESTS_FINAL.log',
                 'GPU_SUPERVISION_NATIVE_AMP_V2_001.log','GPU_SUPERVISION_NATIVE_AMP_V2_002.log',
                 'PRECISION_CORRECTION_PLAN.json','runtime_resource_samples_001.jsonl',
                 'RUNTIME_RESOURCE_SAMPLING_STATUS.json'):
        p=TASK/'private'/name
        if p.exists():copy(p,REVIEW/'09_LOGS'/name)
    for name in ('BUILD_PROGRESS_001','BUILD_PROGRESS_002','START_UNIQUE_BUILD_001',
                 'FORMAL_SOURCE_BLOB_AUDIT_001','FORMAL_SOURCE_LINE_ENDING_AUDIT_001'):
        for suffix in ('.stdout','.stderr','.json'):
            p=TASK/'private/remote'/(name+suffix)
            if p.exists():copy(p,REVIEW/'09_LOGS/native_build_and_source_audit'/p.name)
    diagnostic=TASK/'diagnostics/native_001'
    for p in sorted(diagnostic.rglob('*')):
        if p.is_file() and p.suffix not in ('.gz',):
            copy(p,REVIEW/'03_R2_CADP_DR_INTEGRATION/native_diagnostics'/p.relative_to(diagnostic))
    for p in sorted((TASK/'gpu_results_FP32_PROTOCOL_PILOT_001/receipts_before_relocation').glob('*.json')):
        copy(p,REVIEW/'09_LOGS/FP32_pilot_source_receipts'/p.name)
    for p in sorted((TASK/'evaluation_FP32_PROTOCOL_PILOT_001').glob('*')):
        if p.is_file():copy(p,REVIEW/'09_LOGS/EXCLUDED_FP32_PILOT_METRICS'/p.name)
    for p in sorted((TASK/'gpu_results/cleanup').glob('*.json')):
        copy(p,REVIEW/'09_LOGS/verified_remote_temporary_cleanup'/p.name)
    for p in sorted((TASK/'tests').glob('*.py')):
        copy(p,REVIEW/'08_TESTS'/p.name)
    for folder in ('scripts','gpu','CADP_DR_EXPERIMENTAL_BRANCH','configs'):
        previous=TASK/'source_versions/fp32_protocol_pilot_001'/folder
        for p in sorted(previous.rglob('*')):
            if p.is_file() and acceptable(p):
                copy(p,REVIEW/'09_LOGS/EXCLUDED_FP32_PILOT_SOURCE'/p.relative_to(TASK/'source_versions/fp32_protocol_pilot_001'))


def secrets_check(path):
    if path.suffix.lower() not in ('.py','.json','.csv','.md','.log','.txt','.yaml','.yml','.stdout','.stderr','.patch'):
        return
    raw=path.read_text(encoding='utf-8',errors='replace')
    tests=(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
           r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',
           r'https://[^\s/@]+:[^\s/@]+@',r'(?i)[?&](?:token|access_token|x-amz-signature)=[^\s"\']{16,}')
    if any(re.search(pattern,raw) for pattern in tests):
        raise RuntimeError('Possible access-bearing material in '+str(path))


def main():
    decision=json.loads((REVIEW/'10_FINAL_REPORT/TASK011B_DECISION.json').read_text())
    if decision.get('formal_window_runs')!=140 or decision['status']!='COMPLETED_ACTUAL_140_TERMINAL_OUTCOMES':
        raise RuntimeError('Cannot package an incomplete formal study as final')
    stage_sources()
    files=[p for p in sorted(REVIEW.rglob('*')) if p.is_file() and p!=REVIEW/'SHA256_MANIFEST.csv']
    for p in files:
        if not acceptable(p):raise RuntimeError('Non-publication artifact: '+str(p))
        if p.stat().st_size>=100*1024**2:raise RuntimeError('Split/compact oversized expanded Git evidence: '+str(p))
        secrets_check(p)
    rows=[dict(path=p.relative_to(REVIEW).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    csvwrite(REVIEW/'SHA256_MANIFEST.csv',rows)
    files.append(REVIEW/'SHA256_MANIFEST.csv')
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    if ARCHIVE.exists():raise FileExistsError('Preserve the existing completed review archive')
    with zipfile.ZipFile(ARCHIVE,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files:z.write(p,p.relative_to(REVIEW).as_posix())
    if ARCHIVE.stat().st_size>=2*1024**3:
        raise RuntimeError('Review exceeds per-asset cap; preserve full archive and publish explicit parts')
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC failed')
        for row in rows:
            data=z.read(row['path'])
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                raise RuntimeError('Internal ZIP identity failure')
    archive_sha=sha(ARCHIVE)
    checksum=Path(str(ARCHIVE)+'.sha256')
    checksum.write_text(archive_sha+'  '+ARCHIVE.name+'\n',encoding='ascii')
    # Explicit isolated index only: never stage an untracked tree wholesale.
    candidates=[(p.relative_to(ROOT).as_posix(),p) for p in files]
    for folder in CODE_DIRS:
        candidates += [(p.relative_to(ROOT).as_posix(),p) for p in sorted((TASK/folder).rglob('*')) if p.is_file() and acceptable(p)]
    for name in ('EXECUTION_STATE.md',):candidates.append(((TASK/name).relative_to(ROOT).as_posix(),TASK/name))
    for name in ('README.md','PROJECT_STATUS.md','REVIEW_INDEX.md','CURRENT_RESEARCH_STATUS.md',
                 'CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json','AGENTS.md'):
        p=ROOT/name
        if p.exists():candidates.append((name,p))
    candidates.append((checksum.relative_to(ROOT).as_posix(),checksum))
    entries=[];seen=set()
    for name,p in candidates:
        if name in seen:continue
        seen.add(name);secrets_check(p)
        blob=hashlib.sha1(('blob '+str(p.stat().st_size)+'\0').encode()+p.read_bytes()).hexdigest()
        entries.append(dict(path=name,source=str(p),bytes=p.stat().st_size,sha256=sha(p),git_blob_sha=blob))
    PRIVATE.mkdir(parents=True,exist_ok=True)
    parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dump(PRIVATE/'allowlist.json',dict(parent_sha=parent,branch='task011b/validity-aware-cadp-dr',
        entries=entries,archive=str(ARCHIVE),archive_sha256=archive_sha,review_directory=RELPATH,
        release_tag='task011b-validity-aware-cadp-dr-20261127',internal_sha256_count=len(rows)))
    dump(PRIVATE/'LOCAL_DELIVERY_VERIFICATION.json',dict(status='PASS',ZIP_CRC='PASS',
        internal_sha256_count=len(rows),archive_sha256=archive_sha,archive_bytes=ARCHIVE.stat().st_size,
        raw_datasets_or_weights_included=False,publication_not_yet_performed=True))
    print('FULL_REVIEW_ZIP_AND_EXPLICIT_GIT_ALLOWLIST_READY',len(rows),len(entries),ARCHIVE.stat().st_size,flush=True)


if __name__=='__main__':main()
