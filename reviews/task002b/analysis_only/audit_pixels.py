"""Verify local JPEG identities and replay the pure input transforms on CPU."""

import hashlib
import json
import tempfile
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from audit_common import (FIXED, OUT, RAW_ROOT, ZIP, ZIP_SHA, cpu_guard, digest,
                          exact_member, load_contract, require, save_csv, save_json, sha)

cpu_guard()
import cv2
import numpy as np

cv2.setNumThreads(1)
WH = (640, 360)
RAW_WH = (1920, 1080)
MEAN = np.array([.485, .456, .406], dtype=np.float32)[:, None, None]
STD = np.array([.229, .224, .225], dtype=np.float32)[:, None, None]
ANCHOR = 'val_007_full_00001-00487'
KNOWN_007 = {301, 309, 325, 353}


def preprocess(im, f, m):
    if m['branch'] == FIXED:
        return cv2.resize(im, WH, interpolation=cv2.INTER_LINEAR)
    src = np.asarray(f['source_k'], dtype=np.float64)
    dst = np.asarray(m['output_k'], dtype=np.float64)
    x = (np.arange(WH[0]) - dst[2]) / dst[0] * src[0] + src[2]
    y = (np.arange(WH[1]) - dst[3]) / dst[1] * src[1] + src[3]
    require(x.min() >= 0 and y.min() >= 0 and x.max() <= RAW_WH[0] - 1
            and y.max() <= RAW_WH[1] - 1, 'virtual remap outside source viewport')
    xx, yy = (np.asarray(t, dtype=np.float32) for t in np.meshgrid(x, y))
    return cv2.remap(im, xx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def rgb32(bgr):
    return np.ascontiguousarray(bgr[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32) / np.float32(255)


def audit_pixel_sample(jpeg, frozen_frame, manifest, blob, tmpfile, decoded=None, color=None):
    if decoded is None:
        decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    require(decoded is not None and decoded.shape == (1080, 1920, 3) and decoded.dtype == np.uint8,
            'invalid source JPEG sample')
    # Compare the decode entrypoints actually used by the two pinned runners.
    tmpfile.write_bytes(jpeg)
    wild_bgr = cv2.imread(str(tmpfile), cv2.IMREAD_COLOR)
    require(np.array_equal(decoded, wild_bgr), 'local imread/imdecode pixel mismatch')
    slam_color = preprocess(decoded, frozen_frame, manifest) if color is None else color
    wild_color = preprocess(wild_bgr, frozen_frame, manifest)
    require(slam_color.shape == (360, 640, 3) and np.array_equal(slam_color, wild_color),
            'local resize/remap output mismatch')
    slam_loader = np.ascontiguousarray(slam_color.transpose(2, 0, 1))[None]
    wild_loader = rgb32(wild_color)[None]
    slam_fnet = (slam_loader[:, [2, 1, 0], :, :].astype(np.float32) / np.float32(255) - MEAN) / STD
    wild_fnet = (wild_loader - MEAN) / STD
    require(np.array_equal(slam_fnet, wild_fnet), 'CPU-rebuilt common feature input mismatch')
    return dict(segment=manifest['id'], sequence=manifest['sequence'], environment=manifest['environment'],
                calibration_branch=manifest['branch'], rgb_id=frozen_frame['rgb_id'], zip_member=blob,
                original_jpeg_sha256=frozen_frame['sha256'], decoded_bgr_sha256=sha(decoded.tobytes()),
                resized_or_remapped_bgr_sha256=sha(slam_color.tobytes()),
                slam_bgr_uint8_chw_sha256=sha(slam_loader.tobytes()),
                wild_rgb_float32_chw_sha256=sha(wild_loader.tobytes()),
                slam_cpu_normalized_rgb_f32_sha256=sha(slam_fnet.tobytes()),
                wild_cpu_normalized_rgb_f32_sha256=sha(wild_fnet.tobytes()),
                normalized_f32_min=float(slam_fnet.min()), normalized_f32_max=float(slam_fnet.max()),
                max_abs_feature_input_delta=float(np.max(np.abs(slam_fnet-wild_fnet))),
                local_cv2_version=cv2.__version__, historical_kernel_bitwise_claim=False)


def exact_replay_member(m, f, jpeg):
    decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    require(decoded is not None and decoded.shape == (1080, 1920, 3) and decoded.dtype == np.uint8,
            f'replay decode failed: {m["id"]} {f["rgb_id"]}')
    color = preprocess(decoded, f, m)
    return decoded, color


def main():
    started = time.monotonic()
    require(digest(ZIP) == ZIP_SHA,
            'unrecognized original R2 ZIP')
    per_segment, samples, full_replays, errors = [], [], [], []
    seen = defaultdict(list)
    with ZipFile(ZIP) as z, ExitStack() as stack:
        _, contract = load_contract(z)
        ledger = {r['segment']: r for r in json.loads(exact_member(z, 'evidence/REMOTE_PIXEL_PAIRING.json'))['results']}
        paths = sorted(RAW_ROOT.glob('val_img_*_jpg.zip'))
        require(len(paths) == 5, f'local VIPER Validation JPEG shards expected=5 found={len(paths)}')
        index = defaultdict(list)
        shards = []
        for p in paths:
            src = stack.enter_context(ZipFile(p))
            members = [i for i in src.infolist() if i.filename.startswith('val/img/') and i.filename.endswith('.jpg')]
            shards.append(dict(path=str(p), bytes=p.stat().st_size, indexed_jpegs=len(members)))
            for member in members:
                index[member.filename].append((src, member))
        tmpdir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='pixel_replay_', dir=OUT / 'analysis_only')))
        tmpfile = tmpdir / 'sample.jpg'
        # Replay Night anchor and first complete variable-calibration segment as extra version diagnostics.
        anchor_sids = {ANCHOR}
        anchor_sids.add(next(r['id'] for r in contract if r['branch'] != FIXED))
        for c in contract:
            sid, seq = c['id'], c['sequence']
            raw_manifest = exact_member(z, f'manifests/{sid}.json')
            require(sha(raw_manifest) == c['input_manifest_sha256'], f'input manifest SHA mismatch: {sid}')
            m = json.loads(raw_manifest)
            n = len(m['frames'])
            ids = [int(m['frames'][p]['rgb_id']) for p in (0, n//2, n-1)]
            picks = set(ids) | (KNOWN_007 if seq == 'val_007' else set())
            identities, byte_count, sample_count = set(), 0, 0
            verify_bgr, verify_rgb = hashlib.sha256(), hashlib.sha256()
            replay_count = 0
            for f in m['frames']:
                frame = f['rgb_id']
                k = f'val/img/{seq[-3:]}/{seq[-3:]}_{frame:05d}.jpg'
                try:
                    require(len(index[k]) == 1, f'missing or nonunique archive member: {k}')
                    reader, member = index[k][0]
                    jpeg = reader.read(member)  # ZipFile verifies streamed member CRC.
                    require(len(jpeg) == f['bytes'] and sha(jpeg) == f['sha256'], f'JPEG size or SHA mismatch: {k}')
                    identities.add(frame)
                    byte_count += len(jpeg)
                    seen[f['sha256']].append((seq, frame))
                    decoded, color = None, None
                    if sid in anchor_sids:
                        decoded, color = exact_replay_member(m, f, jpeg)
                        verify_bgr.update(color.tobytes())
                        verify_rgb.update(rgb32(color).tobytes())
                        replay_count += 1
                    if frame in picks:
                        samples.append(audit_pixel_sample(jpeg, f, m, k, tmpfile, decoded, color))
                        sample_count += 1
                except (OSError, ValueError, BadZipFile, cv2.error) as e:
                    errors.append(dict(segment=sid, rgb_id=frame, member=k, error=str(e)))
            per_segment.append(dict(segment=sid, sequence=seq, environment=c['environment'],
                                    calibration_branch=c['branch'], expected_jpegs=n, verified_jpegs=len(identities),
                                    verified_jpeg_bytes=byte_count, cpu_dual_decode_resize_and_normalize_samples=sample_count,
                                    expected_preflight_bgr_sha256=ledger[sid]['bgr_uint8_hwc_sha256'],
                                    expected_wild_tracking_rgb_f32_sha256=c['wild_rgb_tensor_sha256']))
            if sid in anchor_sids:
                br, rg = verify_bgr.hexdigest(), verify_rgb.hexdigest()
                full_replays.append(dict(segment=sid, decoded_frames=replay_count, scheduled_frames=n,
                                         replay_bgr_sha256=br, replay_rgb_f32_sha256=rg,
                                         original_bgr_sha256=ledger[sid]['bgr_uint8_hwc_sha256'],
                                         original_rgb_f32_sha256=c['wild_rgb_tensor_sha256'],
                                         bgr_matches_history=replay_count == n and br == ledger[sid]['bgr_uint8_hwc_sha256'],
                                         rgb_f32_matches_history=replay_count == n and rg == c['wild_rgb_tensor_sha256']))
            if len(per_segment) % 12 == 0:
                print(f'RGB audit {len(per_segment)}/92 segments, {sum(r["verified_jpegs"] for r in per_segment)} verified JPEGs', flush=True)

    repeated = []
    for h, ids in seen.items():
        if len(ids) > 1:
            repeated.append(dict(jpeg_sha256=h, images=len(ids), sequences=len(set(s for s, _ in ids)),
                                 identities=';'.join(f'{s}:{i}' for s, i in ids)))
    bitpath = np.arange(256, dtype=np.float32)[None, :, None]
    divide = (bitpath / np.float32(255) - MEAN) / STD
    mul_recip = (bitpath * np.float32(1/255) - MEAN) / STD
    payload = dict(status='PASS' if not errors else 'PARTIAL', expected_segments=len(contract),
                   scheduled_jpegs=sum(r['expected_jpegs'] for r in per_segment),
                   verified_jpegs=sum(r['verified_jpegs'] for r in per_segment),
                   verified_bytes=sum(r['verified_jpeg_bytes'] for r in per_segment),
                   exact_duplicate_jpeg_hash_groups=len(repeated),
                   exact_cross_sequence_duplicate_jpeg_groups=sum(r['sequences'] > 1 for r in repeated),
                   exact_redundant_jpeg_records=sum(r['images']-1 for r in repeated),
                   cpu_pixel_samples=len(samples), cpu_opencv=cv2.__version__, numpy=np.__version__,
                   historical_opencv='4.8.1',
                   local_full_replays=full_replays,
                   encoder_dtype='float32 in NumPy replay, before convolution/autocast effects',
                   float32_arithmetic_sensitivity=dict(
                       hypothesis='direct division vs multiply by rounded reciprocal, not a device claim',
                       changed_channel_value_combinations=int(np.count_nonzero(divide != mul_recip)),
                       channel_value_combinations=int(divide.size), max_abs_normalized_delta=float(np.max(np.abs(divide-mul_recip)))),
                   shards=shards, exceptions=errors, wall_seconds=time.monotonic()-started)
    save_csv('RGB_SOURCE_SEGMENT_AUDIT.csv', per_segment)
    save_csv('CPU_PREPROCESSING_REPLAY_SAMPLES.csv', samples,
             None if samples else ['segment', 'sequence', 'rgb_id'])
    save_csv('EXACT_JPEG_DUPLICATE_GROUPS.csv', repeated,
             ['jpeg_sha256', 'images', 'sequences', 'identities'])
    save_json('CPU_PIXEL_AUDIT.json', payload)
    print(f'RGB {payload["status"]}: {payload["verified_jpegs"]}/{payload["scheduled_jpegs"]} JPEGs; '
          f'{len(samples)} dual-path CPU pixel samples; {len(errors)} exceptions; {payload["wall_seconds"]:.1f}s', flush=True)
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
