"""Explicit publication allowlist. Large cache arrays stay in the sealed run."""
import csv,hashlib,importlib.util,io,json,re,shutil,zipfile
from pathlib import Path
from common import TASK,ROOT,REVIEW,REVIEW_REL,PARENT,BASE,dump,sha,csvwrite

TAG='task011e-fast-285-storage-stop-20261128'
ARCHIVE=ROOT/'review_packages/GAMECAM_TASK011E_FAST_STORAGE_STOP_REVIEW.zip'

def check(path):
    if path.suffix.lower() in ('.pth','.pt','.so','.dll','.npz','.npy','.jpg','.jpeg','.png','.zip'):
        raise RuntimeError('Raw/binary artifact is not in this review: '+str(path))
    raw=path.read_text(encoding='utf-8')
    patterns=[r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',
        r'github_pat_[A-Za-z0-9_]{30,}',r'https://[^\s/@]+:[^\s/@]+@',r'(?i)[?&](?:access_token|x-amz-signature)=[^\s"\']{16,}']
    if any(re.search(pattern,raw) for pattern in patterns):raise RuntimeError('Access-bearing content must not be published')

def main():
    private=TASK/'private/publication';private.mkdir(parents=True,exist_ok=True)
    if ARCHIVE.exists() or (private/'allowlist.json').exists():raise FileExistsError('Preserve previous package')
    for name in ['prepare_stop_review.py','package_stop_review.py','publish_stop_review.py']:
        target=REVIEW/'reproducibility/experiments/TASK011E'/name;shutil.copy2(TASK/name,target)
    files=sorted(p for p in REVIEW.rglob('*') if p.is_file())
    for path in files:check(path)
    records=[dict(path=p.relative_to(REVIEW).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    csvwrite(REVIEW/'SHA256_MANIFEST.csv',records);files.append(REVIEW/'SHA256_MANIFEST.csv')
    ARCHIVE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:z.write(path,path.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        for r in records:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
    checksum=Path(str(ARCHIVE)+'.sha256');checksum.write_text(sha(ARCHIVE)+'  '+ARCHIVE.name+'\n',encoding='ascii')
    source=json.loads((TASK/'private/PUBLICATION_SOURCE_ALLOWLIST.json').read_text())
    paths=files+[checksum]
    paths.extend(TASK/n for n in source['code']+['README.md','FINAL_REVIEW.md','prepare_stop_review.py','package_stop_review.py','publish_stop_review.py'])
    paths.extend(p for folder in ['configs','frozen_metrics','reports','intake','evidence'] for p in (TASK/folder).rglob('*') if p.is_file())
    paths.extend(TASK/n for n in ['MODEL_WEIGHT_IDENTITY.json','GPU_PREFLIGHT_REPORT.json','RUNTIME_AUTHORIZATION.json',
        'CACHE_MANIFEST.csv','E2E_EXECUTION_LEDGER.csv','BATCH_CHECKPOINT.json','FAILURE_ACCOUNTING.json','TRAJECTORY_METRICS.csv',
        'PRIMARY_PAIRED_BOOTSTRAP.json','STRICT_THREE_SEEDS_SENSITIVITY.json','PER_WEATHER_FAILURE_ACCOUNTING.json'])
    paths.extend(ROOT/n for n in ['README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md','REVIEW_INDEX.md'])
    entries=[];seen=set()
    for p in paths:
        name=p.relative_to(ROOT).as_posix()
        if name in seen:continue
        seen.add(name);check(p);raw=p.read_bytes()
        entries.append(dict(path=name,source=str(p),bytes=len(raw),sha256=sha(p),
            git_blob_sha=hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()))
    dump(private/'allowlist.json',dict(parent_sha=PARENT,branch='codex/task011e-fast-285-20261128',review_directory=REVIEW_REL,
        archive=str(ARCHIVE),archive_sha256=sha(ARCHIVE),internal_sha256_count=len(records),release_tag=TAG,entries=entries))
    dump(private/'LOCAL_DELIVERY_VERIFICATION.json',dict(status='PASS',ZIP_CRC='PASS',internal_files=len(records),
        bytes=ARCHIVE.stat().st_size,sha256=sha(ARCHIVE),credentials_raw_data_weights_included=False))
    canonical=BASE/REVIEW_REL
    if canonical.exists():raise FileExistsError('Canonical review already exists')
    shutil.copytree(REVIEW,canonical)
    print(json.dumps(dict(status='ZIP_CRC_AND_SHA_PASS',internal_SHA=len(records),expanded_paths=len(entries),
        bytes=ARCHIVE.stat().st_size,sha256=sha(ARCHIVE))))

if __name__=='__main__':main()
