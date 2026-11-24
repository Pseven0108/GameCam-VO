"""Verify and stage the approved observer without loading a model."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPLOAD = ROOT / 'incoming'
ORIGIN = ROOT.parent / 'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408'
SOURCE = ORIGIN / 'source/DROID-W'
R2 = ROOT.parent / 'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
SEGMENT = 'val_007_full_00001-00487'
COMMIT = 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'
HOST = 'jupyter-6g08vd8ezmzwvd1k'
CODE = ROOT / 'source/DROID-W'
INPUT = ROOT / 'inputs' / SEGMENT
LOCKED = {
    'TASK003_INSTRUMENTATION_PATCH.diff': '177e085d368c4f45d094b4c127f3a58d908ba145c893e20da24308d51964be21',
    'TASK003_RUNTIME_CONFIG.json': 'a2456c1adfcd2f4702c4a1e51dc35d67ad0cfa5e1272ed965206e97769498a69',
    'PATCH_VERIFICATION.json': '8f36c23651f641b7ab45645393e0d68b13f7c9c555846486e32926923438027d',
    'task003_run_segment.py': '058ef44f50f81bea2d3adfbd7d602ad8c924da298478dc79e6b6ba33e621c1f3',
    'task003_observer.py': '7b34c8f34370e7a1e0663d32709f421cfd1be8c476b6f95c0ee1e75804e41804',
    'native_config.yaml': 'a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc',
    'INPUT.json': '5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537',
}
PIPE = {'segment_input.py': 'eb5afb40b87fd56995138f916944637566ec59a4f3b2b84a4f96cf795a1d6903',
        'transfer_common.py': '4f91e5f39375575640f1034fc6aff02ef06dfd342f1e4741c4da68b70e5627e4'}


def digest(path):
    with Path(path).open('rb') as f:
        h = hashlib.sha256()
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require(condition, why):
    if not condition:
        raise RuntimeError(why)


def check(path, sha):
    actual = digest(path)
    require(actual == sha, f'SHA mismatch: {path} ({actual})')
    return dict(path=str(path), sha256=actual, bytes=path.stat().st_size)


def unique_json(path, info):
    with path.open('x', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def stage():
    require(socket.gethostname() == HOST, 'Unexpected SSH target')
    require(ROOT == Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1'), 'Unexpected run root')
    require(not CODE.exists() and not INPUT.exists() and not (ROOT / 'ONE_RUN_CLAIM').exists(), 'Staging is not fresh')
    require(shutil.disk_usage(ROOT).free >= 10 * 1024**3, 'Insufficient staging space')
    uploaded = [check(UPLOAD / name, sha) for name, sha in LOCKED.items()]
    cfg = read(UPLOAD / 'TASK003_RUNTIME_CONFIG.json')
    require(cfg['assets']['commit'] == COMMIT and read(SOURCE / '.official_archive.json')['commit'] == COMMIT, 'Wrong upstream commit')
    patch = read(UPLOAD / 'PATCH_VERIFICATION.json')['file_hashes']
    base = [check(SOURCE / f['path'], f['before_sha256']) for f in patch if f['before_sha256'] is not None]
    ext = cfg['assets']['extension']
    extension = check(Path(ext['path']), ext['sha256'])
    require(all(Path(w['path']).is_relative_to(ORIGIN / 'data') for w in cfg['assets']['weights']), 'Bad weight path')
    weights = [check(Path(w['path']), w['expected_sha256']) for w in cfg['assets']['weights']]
    pipeline = [check(R2 / 'pipeline' / n, h) for n, h in PIPE.items()]
    rgb = Path(cfg['assets']['rgb_cache'])
    require(rgb == ORIGIN / 'data/val_007', 'RGB root mismatch')
    doc = read(UPLOAD / 'INPUT.json')
    require(doc['id'] == SEGMENT and doc['branch'] == 'FIXED_K_NATIVE_RESIZE' and doc['stride'] == 1
            and doc['out_wh'] == [640, 360] and [f['rgb_id'] for f in doc['frames']] == list(range(1, 488)), 'RGB input drift')
    rgb_bytes = 0
    for frame in doc['frames']:
        require(frame['file'] == f"{frame['rgb_id']:05d}.jpg", 'Bad RGB member')
        path = rgb / frame['file']
        require(not path.is_symlink() and path.stat().st_size == frame['bytes'], f'Bad RGB file: {path.name}')
        rgb_bytes += check(path, frame['sha256'])['bytes']
    print('Verified 487 JPEGs, four weight files and the CUDA extension.', flush=True)
    CODE.parent.mkdir(exist_ok=True)
    subprocess.run(['cp', '-a', '--reflink=auto', str(SOURCE), str(CODE)], check=True)
    delta = UPLOAD / 'TASK003_INSTRUMENTATION_PATCH.diff'
    for args in (['--check'], []):
        subprocess.run(['git', 'apply', *args, str(delta)], cwd=CODE, check=True)
    patched = [check(CODE / f['path'], f['after_sha256']) for f in patch]
    check(CODE / 'task003_observer.py', LOCKED['task003_observer.py'])
    copied_ext = check(CODE / Path(ext['path']).name, ext['sha256'])
    p = ROOT / 'pipeline'
    p.mkdir()
    for name, sha in PIPE.items():
        shutil.copyfile(R2 / 'pipeline' / name, p / name)
        check(p / name, sha)
    shutil.copyfile(UPLOAD / 'task003_run_segment.py', p / 'task003_run_segment.py')
    check(p / 'task003_run_segment.py', LOCKED['task003_run_segment.py'])
    INPUT.mkdir(parents=True)
    for frame in doc['frames']:
        (INPUT / frame['file']).symlink_to(rgb / frame['file'])
    shutil.copyfile(UPLOAD / 'INPUT.json', INPUT / 'INPUT.json')
    check(INPUT / 'INPUT.json', LOCKED['INPUT.json'])
    unique_json(ROOT / 'evidence/STAGE_VERIFICATION.json', dict(status='STAGED_NO_MODEL_STARTED',
        utc=datetime.now(timezone.utc).isoformat(), server=HOST,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        source_commit=COMMIT, staged_source=str(CODE), historical_source=str(SOURCE),
        uploaded=uploaded, base_hashes=base, patched_hashes=patched, weights=weights, extension=extension,
        staged_extension=copied_ext, pipeline=pipeline, image_count=len(doc['frames']), image_bytes=rgb_bytes,
        image_root=str(rgb), gt_uploaded=0, model_started=False))
    print('Verified observer postimage hashes. Staged, run still 0/1.', flush=True)


if __name__ == '__main__':
    stage()
