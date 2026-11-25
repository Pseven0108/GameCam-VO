"""Read-only intake. Never imports a baseline, Torch, a model or a tensor archive."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
R0 = PROJECT / 'experiments/GAMECAM_TASK006A_R0_CADP_SOURCE_CONFIG_AUDIT_20261126_R1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('Set CUDA_VISIBLE_DEVICES to the empty string')
    receipt = ROOT / 'evidence/PRESERVATION_BEFORE.json'
    if receipt.exists():
        raise RuntimeError('Intake already sealed; do not overwrite')
    originals = [p for p in R0.rglob('*') if p.is_file()]
    copies = json.loads((R0 / 'evidence/SOURCE_AND_EVIDENCE_COPIES.json').read_text(encoding='utf-8'))['files']
    originals += [Path(x['source']) for x in copies if Path(x['source']).is_file()]
    originals += [PROJECT / 'docs/TASK006A_PROGRESS.md']
    rows = []
    for p in sorted(set(originals)):
        st = p.stat()
        rows.append({'path': str(p), 'sha256': sha(p), 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns})
    write_json(receipt, {'created': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'files': rows,
                         'scope': 'All R0 deliverables and referenced existing source/config text; no C0/tensor/model read'})
    include = ['FINAL_REVIEW.md','AUDIT_DECISION.json','TASK006A_R0_MATHEMATICAL_ENDPOINT_AUDIT.md',
               'TASK006A_R0_COVARIANCE_TENSOR_LIFECYCLE.md','TASK006A_R0_REFERENCE_TRANSFER_AUDIT.md',
               'TASK006A_R0_CONFIG_RECONCILIATION.md','evidence/PI3MOS_SOURCE_RECEIPTS.json',
               'evidence/GAMMA_DEPTH_EVIDENCE.json','evidence/configs/r2_sealed_config.yaml',
               'evidence/sources/DROID-W-official/src/lib/droid_kernels.cu',
               'evidence/sources/DROID-W-official/src/lib/droid.cpp',
               'evidence/sources/DROID-W-official/LICENSE',
               'evidence/sources/Pi3MOS-1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/fastba/ba_cuda.cu',
               'evidence/sources/Pi3MOS-1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/config.py']
    source_rows = []
    for rel in include:
        src = R0 / rel
        dst = ROOT / 'evidence/R0' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise RuntimeError('Evidence destination exists')
        shutil.copyfile(src, dst)
        source_rows.append({'source': str(src), 'copy': str(dst.relative_to(ROOT)), 'sha256': sha(dst)})
    config = R0 / 'evidence/configs/r2_sealed_config.yaml'
    assert sha(config) == 'a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc'
    archive = R0 / 'deliveries/GAMECAM_TASK006A_R0_CADP_REVIEW.zip'
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        assert bad is None
        names = z.namelist()
    write_json(ROOT / 'evidence/INTAKE_VERIFICATION.json', {
        'R0_zip_sha256': sha(archive), 'R0_zip_CRC_PASS': bad is None, 'R0_zip_members': len(names),
        'effective_gamma_depth': 0.01, 'R2_config_sha256': sha(config),
        'DROID_W_commit': 'c3414af6047d06bafc1a6645d09f23247f3b2cdc',
        'Pi3MOS_commit': '1b81d729c4259a5a775eb4aae41f959eea38ae14',
        'Pi3MOS_remote_head_rechecked': True,
        'Pi3MOS_official_source': 'https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/fastba/ba_cuda.cu#L549',
        'copies': source_rows, 'checkpoint_deserialized': False, 'R0_payload_manifest_recomputed': False})
    import numpy
    import scipy
    write_json(ROOT / 'evidence/ENVIRONMENT.json', {
        'python': sys.version, 'executable': sys.executable, 'numpy': numpy.__version__, 'scipy': scipy.__version__,
        'CUDA_VISIBLE_DEVICES': os.environ['CUDA_VISIBLE_DEVICES'],
        'OPENBLAS_NUM_THREADS': os.environ.get('OPENBLAS_NUM_THREADS'),
        'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS'), 'new_packages_installed': False,
        'free_disk_bytes': shutil.disk_usage(ROOT).free})
    print(json.dumps({'protected_files': len(rows), 'copied_text_files': len(source_rows), 'R0_CRC': 'PASS'}))


if __name__ == '__main__':
    main()
