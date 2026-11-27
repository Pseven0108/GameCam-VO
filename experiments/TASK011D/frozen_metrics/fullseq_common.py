"""Read already admitted VIPER RGB manifests; never open pose labels."""
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
cv2.setNumThreads(1)


def atomic_json(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def sha_file(path):
    with Path(path).open('rb') as f:
        digest = hashlib.sha256()
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def status(out, phase, **extra):
    value = {'phase': phase, 'time_unix': time.time(), **extra}
    atomic_json(out / 'progress.json', value)
    print(f'CAMVO {json.dumps(value, sort_keys=True)}', flush=True)


def viper_frames(case, stride):
    data = ROOT / 'data' / case
    raw = data / 'INPUT.json'
    manifest = json.loads(raw.read_text(encoding='utf-8'))
    assert case == f'{manifest["split"]}_{manifest["sequence"]}'
    assert manifest['orig_size'] == [1920, 1080] and manifest['proc_size'] == [640, 360]
    records = manifest['frames']
    ids = [x['rgb_id'] for x in records]
    assert ids and ids == list(range(ids[0], ids[-1] + 1)), 'noncontiguous source IDs'
    for row in records:
        assert row['file'] == f'{row["rgb_id"]:05d}.jpg'
        assert (data / row['file']).stat().st_size == row['bytes'], row['file']
    k = np.asarray(manifest['calibration'], dtype=np.float32)
    assert k.shape == (4,) and np.isfinite(k).all() and min(k[:2]) > 0
    selected = [(r['rgb_id'], data / r['file'], r['sha256']) for r in records[::stride]]
    return selected, k, sha_file(raw), len(records)


def bgr_frame(path, expected_sha=None):
    raw = path.read_bytes()
    if expected_sha is not None and hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError(f'input hash mismatch: {path}')
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f'invalid RGB frame: {path}')
    return image


def write_result(out, poses, ids, **extra):
    poses = np.asarray(poses, dtype=np.float64)
    ids = np.asarray(ids, dtype=np.int64)
    assert poses.shape == (len(ids), 7), (poses.shape, len(ids))
    good = np.isfinite(poses).all(axis=1) & (np.abs(np.linalg.norm(poses[:, 3:], axis=1)-1) < .002)
    np.savez_compressed(out / 'trajectory.npz', rgb_ids=ids, c2w_xyzw=poses, finite_valid=good)
    result = {'input_frames': len(ids), 'poses_exported': len(poses), 'valid_poses': int(np.sum(good)),
              'trajectory_sha256': sha_file(out / 'trajectory.npz'), **extra}
    if not good.all():
        atomic_json(out / 'invalid_export.json', result)
        raise ValueError('INVALID_POSE_EXPORT')
    atomic_json(out / 'model_result.json', result)
