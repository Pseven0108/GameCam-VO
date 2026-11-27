"""Explicit current-stage allowlist, full ZIP, CRC/SHA verification; no push."""
import csv
import hashlib
import json
import re
from pathlib import Path
import shutil
import zipfile

from common import BASE,PARENT,REVIEW,REVIEW_REL,ROOT,TASK,csvwrite,dump,sha

TAG = 'task011d-a7-gpu-adapter-dual-validation-20261128'
ARCHIVE = ROOT/'review_packages/GAMECAM_TASK011D_A7_GPU_ADAPTER_DUAL_VALIDATION_REVIEW.zip'


def check_public(path):
    if path.suffix.lower() in ('.so','.dll','.exe','.whl','.pth','.pt','.ckpt','.safetensors',
                              '.jpg','.jpeg','.png','.exr','.npz','.npy'):
        raise RuntimeError('Unapproved raw/binary artifact in this CPU review: '+str(path))
    raw = path.read_text(encoding='utf-8')
    patterns = (r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
        r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',
        r'https://[^\s/@]+:[^\s/@]+@',r'(?i)[?&](?:access_token|x-amz-signature)=[^\s"\']{16,}')
    if any(re.search(pattern,raw) for pattern in patterns):
        raise RuntimeError('Access-bearing material must not be published')
    if path.stat().st_size >= 100*1024**2:
        raise RuntimeError('Oversized expanded review file')


def main():
    private = TASK/'private/publication'
    private.mkdir(parents=True,exist_ok=True)
    if ARCHIVE.exists() or (private/'allowlist.json').exists():
        raise FileExistsError('Preserve previous delivery/archive state')
    # Refresh the code mirror with final assembly/publication scripts. Do not
    # recursively copy private publication state into its own review.
    for path in sorted(TASK.glob('*.py')):
        target = REVIEW/'reproducibility/experiments/TASK011C'/path.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    files = [p for p in sorted(REVIEW.rglob('*')) if p.is_file() and p.name!='SHA256_MANIFEST.csv']
    for path in files:check_public(path)
    records = [dict(path=p.relative_to(REVIEW).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    csvwrite(REVIEW/'SHA256_MANIFEST.csv',records)
    files.append(REVIEW/'SHA256_MANIFEST.csv')
    ARCHIVE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:z.write(path,path.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.testzip() is not None:raise RuntimeError('Local review ZIP CRC failure')
        for row in records:
            raw = z.read(row['path'])
            if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
                raise RuntimeError('Local review ZIP SHA failure')
    identity = sha(ARCHIVE)
    checksum = Path(str(ARCHIVE)+'.sha256')
    checksum.write_text(identity+'  '+ARCHIVE.name+'\n',encoding='ascii')
    # Only own new code, the new expanded review and explicit status paths.
    candidates = files+[checksum]
    for path in sorted(TASK.rglob('*')):
        if not path.is_file() or any(x in path.parts for x in ('private','__pycache__')):
            continue
        rel = path.relative_to(TASK)
        if rel.parts[0] == 'data_audit':
            continue  # incomplete duplicate census; failure is documented
        candidates.append(path)
    for name in ('README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md','REVIEW_INDEX.md',
                 'CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json'):
        candidates.append(ROOT/name)
    entries = []
    seen = set()
    for path in candidates:
        name = path.relative_to(ROOT).as_posix()
        if name in seen:continue
        seen.add(name)
        check_public(path)
        raw = path.read_bytes()
        entries.append(dict(path=name,source=str(path),bytes=len(raw),sha256=sha(path),
            git_blob_sha=hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()))
    manifest = dict(parent_sha=PARENT,branch='codex/task011d-a7-gpu-adapter-dual-validation-20261128',
        review_directory=REVIEW_REL,archive=str(ARCHIVE),archive_sha256=identity,
        internal_sha256_count=len(records),release_tag=TAG,entries=entries)
    dump(private/'allowlist.json',manifest)
    dump(private/'LOCAL_DELIVERY_VERIFICATION.json',dict(status='PASS',ZIP_CRC='PASS',
        files=len(records),archive_bytes=ARCHIVE.stat().st_size,archive_sha256=identity,
        credentials_raw_data_weights_included=False))
    # Bring the canonical expanded review to the exact packaged byte version.
    for path in files:
        target = BASE/REVIEW_REL/path.relative_to(REVIEW)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=path.read_bytes():
            # These are the current stage's own initial mirror, not history.
            if target.name!='SHA256_MANIFEST.csv' and 'reproducibility' not in target.parts:
                raise RuntimeError('Unexpected canonical review drift')
        shutil.copy2(path,target)
    print(json.dumps(dict(status='LOCAL_REVIEW_VERIFIED',files=len(records),
        staged_paths=len(entries),ZIP_bytes=ARCHIVE.stat().st_size,sha256=identity)))


if __name__ == '__main__':
    main()
