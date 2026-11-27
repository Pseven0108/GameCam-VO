"""Build a full review plus separately indexed original float-array archives."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
REVIEW=ROOT/'reviews/task010a-dynamic-geometry-20261127'
PRIVATE=TASK/'private/publication'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def secret_check(path):
    if path.suffix.lower() not in ['.py','.sh','.json','.csv','.md','.txt','.yaml','.log']:return
    text=path.read_text(encoding='utf-8',errors='replace')
    patterns=[r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}',
        r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',r'AKIA[0-9A-Z]{16}']
    if any(re.search(p,text) for p in patterns):raise RuntimeError('Potential credential material; blocked file '+path.name)


def main():
    if not (TASK/'08_reports/FINAL_REPORT.md').exists():raise RuntimeError('Final research report required')
    if not (TASK/'09_reproducibility/RAW_EVIDENCE_ASSET_INDEX.json').exists():raise RuntimeError('Full raw asset identities required')
    if REVIEW.exists():raise RuntimeError('Review build directory already exists; do not overwrite uncertain or sealed content')
    PRIVATE.mkdir(parents=True,exist_ok=True);REVIEW.mkdir(parents=True)
    for directory in TASK.iterdir():
        if not directory.is_dir() or directory.name in ['private','outputs','__pycache__']:continue
        for source in sorted(directory.rglob('*')):
            if not source.is_file() or '__pycache__' in source.parts or source.suffix in ['.pyc','.pyd','.so','.pth','.pt','.safetensors']:continue
            rel=source.relative_to(TASK);target=REVIEW/rel
            secret_check(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    # All native trajectories, keyframes, configs, native logs and TensorBoard
    # events are small and included in full, not only the winning runs.
    for source in sorted((TASK/'outputs/droid').rglob('*')):
        if not source.is_file():continue
        rel=source.relative_to(TASK/'outputs');target=REVIEW/'raw_native_results'/rel
        secret_check(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for source in sorted((TASK/'private').iterdir()):
        if not source.is_file():continue
        include=(source.name.startswith(('job_','resources_','cpu_tests_')) or source.name.endswith('_STATE.json') or
            source.name in ['development_plan.json','full_geo_smoke_plan.json','full_geo_expansion_plan.json',
                'FORKSERVER_TRANSFER_READY.json','FORKSERVER_HOLDOUT_READY.json','schur_gate_math.log','full_geo_smoke_r2_plan.json',
                'native_import_profile.log','native_cpu_warm_imports.log','forkserver_controller_r2.log',
                'forkserver_holdout_launcher.log','after_full_smoke.log','after_full_smoke_r2.log','offload_gpu_probe.log'])
        if include:
            secret_check(source);target=REVIEW/'execution_logs'/source.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
    for model in ['gmos','pi3mos','geomotion','geomotion_full']:
        for receipt in sorted((TASK/'outputs'/model).glob('*/receipt.json')):
            target=REVIEW/'model_receipts'/model/receipt.parent.name/receipt.name
            secret_check(receipt);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(receipt,target)
        # Fixed examples, not selected for attractive masks or favourable metrics.
        for dataset,fid in [('night007_dev',317),('downtown1_holdout',617)]:
            source=TASK/'outputs'/model/dataset/f'{fid:05d}.npz'
            target=REVIEW/'original_float_samples'/model/dataset/source.name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    authorization=Path('C:/Users/Administrator/.codex/attachments/ad7ed90d-0314-4cef-876a-573263b31d17/已粘贴的文本.txt')
    shutil.copyfile(authorization,REVIEW/'TASK_AUTHORIZATION.zh-CN.txt')
    final=(TASK/'08_reports/FINAL_REPORT.md').read_text(encoding='utf-8')
    (REVIEW/'FINAL_REVIEW.md').write_text(final,encoding='utf-8')
    (REVIEW/'START_HERE.md').write_text('''# TASK010-A review entry

Read [FINAL_REVIEW.md](FINAL_REVIEW.md), the frozen transfer selection, all-run table and paired summary first.

- All code, source versions, tests, configs, original native logs/trajectories and visual evidence are included here.
- Full original model/flow/depth arrays are delivered in six Release ZIPs indexed by `09_reproducibility/RAW_EVIDENCE_ASSET_INDEX.json`. Eight unaltered float examples are also included directly. No arrays have been replaced with screenshots.
- Raw RGB, reference GT, pretrained weights, external model source archives, environment binaries and credentials are excluded. Original local experimental evidence remains intact.
- `SHA256_MANIFEST.csv` covers every package member except itself. External ZIP SHA is provided separately. Actual research limits, failures and non-results must be read with the tables.
''',encoding='utf-8')
    members=sorted(p for p in REVIEW.rglob('*') if p.is_file())
    records=[{'path':p.relative_to(REVIEW).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in members]
    manifest=io.StringIO();w=csv.DictWriter(manifest,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(records)
    (REVIEW/'SHA256_MANIFEST.csv').write_text(manifest.getvalue(),encoding='utf-8',newline='')
    archive=ROOT/'review_packages/GAMECAM_TASK010A_REVIEW.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(REVIEW.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(REVIEW).as_posix())
    if archive.stat().st_size>=95*1024**2:raise RuntimeError('Main review exceeds bounded Git blob size; raw arrays remain in Release assets')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('Review CRC failure')
        for r in records:
            data=z.read(r['path'])
            if len(data)!=r['bytes'] or hashlib.sha256(data).hexdigest()!=r['sha256']:raise RuntimeError('Internal review SHA mismatch')
    identity=sha(archive);archive.with_suffix('.zip.sha256').write_text(identity+'  '+archive.name+'\n')
    proof={'status':'PASS','zip_sha256':identity,'zip_bytes':archive.stat().st_size,
        'zip_members':len(records)+1,'internal_sha256_verified':len(records),'zip_crc':'PASS',
        'full_original_native_results_included':True,'full_original_model_arrays_in_separate_release_assets':True}
    (ROOT/'deliveries').mkdir(exist_ok=True)
    (ROOT/'deliveries/TASK010A_PACKAGE_VERIFICATION.json').write_text(json.dumps(proof,indent=2))
    paths=list(REVIEW.rglob('*'))+[archive,archive.with_suffix('.zip.sha256'),ROOT/'deliveries/TASK010A_PACKAGE_VERIFICATION.json']
    paths += [ROOT/x for x in ['README.md','PROJECT_STATUS.md','REVIEW_INDEX.md','.gitignore']]
    paths += [p for base in [TASK/'scripts',TASK/'tests'] for p in base.glob('*') if p.is_file() and p.suffix in ['.py','.sh']]
    entries=[]
    for p in sorted(set(paths)):
        if not p.is_file():continue
        secret_check(p);data=p.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        entries.append({'path':p.relative_to(ROOT).as_posix(),'source':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob_sha':blob})
    (PRIVATE/'allowlist.json').write_text(json.dumps({'parent_sha':'ff0c9ed761dbcdd6d2fe7b2cda5651c6e173efe1',
        'branch':'codex/task010-a-review-20261127','entries':entries},indent=2))
    print(json.dumps(proof,indent=2));print('Explicit publication allowlist',len(entries))


if __name__=='__main__':main()
