"""Read-only CPU reconstruction of frozen VIPER camera inputs."""

import csv
import io
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

from audit_common import (FIXED, OUT, R1, VIRTUAL, ZIP, cpu_guard, digest, exact_member,
                          load_contract, read_csv, read_json, require, save_csv, save_json, sha)

cpu_guard()
import numpy as np


def run():
    ledger_path = R1 / 'evidence/camera_provenance.json'
    ledger_sha = digest(ledger_path)
    seal = next(r for r in read_json(R1/'FILE_SHA256_MANIFEST.json')['files']
                if r['path'] == 'evidence/camera_provenance.json')
    require(ledger_sha == seal['sha256'] and ledger_path.stat().st_size == seal['bytes'], 'R1 camera ledger seal')
    ledger = read_json(ledger_path)
    val = {r['case']: r for r in ledger['files'] if r['case'].startswith('val_')}
    sources = {r['camera_archive'] for r in val.values()}
    require(len(val) == 47 and len(sources) == 1, 'Validation source inventory')
    raw = Path(next(iter(sources)))
    raw_sha = digest(raw)
    require(raw_sha == ledger['source_sha256']['val'], 'official camera archive SHA-256')
    receipts = {r['segment']: r for r in read_csv(OUT/'R2_RUNTIME_INPUT_RECEIPT_PARITY.csv')}
    sequences, segments = [], []
    with ZipFile(ZIP) as z, ZipFile(raw) as cam:
        _, frozen = load_contract(z)
        groups = defaultdict(list)
        for r in frozen:
            groups[r['sequence']].append(r)
        require(set(groups) == set(val) and set(receipts) == {r['id'] for r in frozen}, 'frozen coverage')
        names = [n for n in cam.namelist() if n.lower().endswith('.csv')]
        require(sorted(names) == sorted(r['member'] for r in val.values()), 'camera member inventory')
        for seq, plan in sorted(groups.items()):
            info = val[seq]
            payload = cam.read(info['member'])  # ZIP read verifies CRC.
            require(sha(payload) == info['member_sha256'], f'{seq}: Camera CSV hash')
            text = payload.decode('utf-8-sig')
            columns = ['frame'] + [f'{p}{i}{j}' for p in 'pv' for i in range(1, 5) for j in range(1, 5)]
            require(next(csv.reader(io.StringIO(text))) == columns, f'{seq}: Camera CSV schema')
            values = np.loadtxt(io.StringIO(text), delimiter=',', skiprows=1, ndmin=2)
            n = info['camera_count']
            require(values.shape == (n, 33) and np.isfinite(values).all()
                    and np.array_equal(values[:, 0], np.arange(n)), f'{seq}: raw camera indexing')
            p = values[:, 1:17].reshape(-1, 4, 4)
            k = np.column_stack((960 * p[:, 0, 0], 540 * p[:, 1, 1],
                                 960 * (1 - p[:, 0, 2]) - .5, 540 * (1 + p[:, 1, 2]) - .5))
            sealed = R1 / 'calibration' / f'{seq}.npy'
            k_sha = digest(sealed)
            require((k[:, :2] > 0).all() and k_sha == info['calibration_sha256']
                    and np.array_equal(k, np.load(sealed, allow_pickle=False)), f'{seq}: reconstructed raw K')
            gt_sha = digest(R1 / 'offline_gt' / f'{seq}.npz')
            require(gt_sha == info['gt_sha256'] and all(r['gt_sha256'] == gt_sha for r in plan),
                    f'{seq}: GT hash lineage')
            spans = np.ptp(k, axis=0)
            branch = VIRTUAL if spans.max() > .001 else FIXED
            require(all(r['branch'] == branch for r in plan), f'{seq}: calibration branch differs')
            if branch == VIRTUAL:
                center = np.array([959.5, 539.5])
                room = np.minimum(k[:, 2:]-.5, np.array([1918.5, 1078.5])-k[:, 2:])
                require((room > 0).all(), f'{seq}: source viewport')
                source = np.r_[(k[:, :2]*center/room).max(axis=0), center]
            else:
                source = k[0]
            down = (source + [0, 0, .5, .5])/3 - [0, 0, .5, .5]
            sequences.append(dict(sequence=seq, branch=branch, camera_member=info['member'],
                                  member_sha256=info['member_sha256'], calibration_sha256=k_sha,
                                  gt_sha256=gt_sha, source_rows=n, segments=len(plan),
                                  k_first=k[0].tolist(), k_min=k.min(0).tolist(), k_max=k.max(0).tolist(),
                                  k_span_px=spans.tolist(), fixed_or_virtual_source_k=source.tolist(),
                                  nominal_output_k=down.tolist(), raw_csv_to_sealed_k_max_abs_px=0.0))
            coverage = []
            for row in sorted(plan, key=lambda x: int(x['first'])):
                sid = row['id']
                member = f'manifests/{sid}.json'
                payload = exact_member(z, member)
                require(sha(payload) == row['input_manifest_sha256'] and payload == (R1/member).read_bytes(),
                        f'{sid}: R1/R2 input manifest mismatch')
                m = json.loads(payload)
                ids = np.array([f['rgb_id'] for f in m['frames']], dtype=np.int64)
                require(len(ids) == int(row['frames']) and np.array_equal(ids, np.arange(int(row['first']),
                                                                                       int(row['last'])+1))
                        and ids[0] >= 1 and ids[-1] <= n, f'{sid}: RGB IDs')
                coverage.extend(ids.tolist())
                src_err = float(np.max(np.abs(source - m['fixed_source_k'])))
                out_err = float(np.max(np.abs(down - m['output_k'])))
                require(max(src_err, out_err) <= 1e-10, f'{sid}: output K reconstruction')
                remap_rows, margin = 0, None
                if branch == VIRTUAL:
                    sk = np.array([f['source_k'] for f in m['frames']])
                    require(np.array_equal(sk, k[ids-1]), f'{sid}: per-frame remap K')
                    low = sk[:, 2:] - down[2:]/down[:2]*sk[:, :2]
                    high = sk[:, 2:] + (np.array([639, 359])-down[2:])/down[:2]*sk[:, :2]
                    margin = float(min(low.min(), (np.array([1919, 1079])-high).min()))
                    require(margin >= 0, f'{sid}: remap outside source image')
                    remap_rows = len(ids)
                else:
                    require(all('source_k' not in f for f in m['frames']), f'{sid}: unexpected frame K')
                rec = receipts[sid]
                actual = np.asarray(json.loads(rec['effective_k_640x360']), dtype=np.float32)
                k8 = np.asarray(json.loads(rec['k_div8_f32']), dtype=np.float32)
                frozen_k = np.asarray(json.loads(row['actual_loader_k']), dtype=np.float32)
                require(rec['loader_k_f32_bitwise_equal'] == 'True'
                        and np.array_equal(actual.view('u4'), frozen_k.view('u4'))
                        and np.array_equal((actual/np.float32(8)).view('u4'), k8.view('u4')), f'{sid}: receipt K bits')
                segments.append(dict(segment=sid, sequence=seq, branch=branch, frames=len(ids),
                                     first_camera_id=int(ids[0]-1), last_camera_id=int(ids[-1]-1),
                                     source_k_max_abs_px=src_err, nominal_k_max_abs_px=out_err,
                                     runtime_k_both_models_bitwise_equal_f32=True,
                                     runtime_k_minus_nominal_max_abs_px=float(np.max(np.abs(actual-down))),
                                     per_frame_virtual_source_k_verified=remap_rows,
                                     minimum_remap_source_margin_px=margin, actual_loader_k_f32=actual.tolist(),
                                     k_div8_f32=k8.tolist()))
            require(coverage == list(range(1, n+1)), f'{seq}: source frames not covered one-to-one')
    require(len(segments) == 92 and sum(r['source_rows'] for r in sequences) == 49815, 'total K coverage')
    save_csv('R2_CAMERA_K_PROVENANCE_BY_SEQUENCE.csv', sequences)
    save_csv('R2_CAMERA_K_PROVENANCE_BY_SEGMENT.csv', segments)
    result = dict(status='PASS', camera_archive=str(raw), camera_archive_bytes=raw.stat().st_size,
                  camera_archive_sha256=raw_sha, camera_provenance_sha256=ledger_sha,
                  raw_camera_member_crc_and_sha256_verified=len(sequences),
                  sealed_calibration_arrays_verified=len(sequences),
                  raw_K_exactly_reconstructed_rows=sum(r['source_rows'] for r in sequences),
                  verified_fixed_segments=sum(r['branch'] == FIXED for r in segments),
                  verified_virtual_segments=sum(r['branch'] == VIRTUAL for r in segments),
                  verified_per_frame_virtual_source_K_rows=sum(r['per_frame_virtual_source_k_verified'] for r in segments),
                  max_nominal_K_reconstruction_error_px=max(r['nominal_k_max_abs_px'] for r in segments),
                  max_runtime_K_minus_nominal_error_px=max(r['runtime_k_minus_nominal_max_abs_px'] for r in segments),
                  minimum_virtual_remap_source_margin_px=min(r['minimum_remap_source_margin_px'] for r in segments
                                                              if r['branch'] == VIRTUAL),
                  camera_id_mapping='RGB_ID-1', camera_physical_clock_verified=False)
    save_json('R2_CAMERA_K_PROVENANCE_AUDIT.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
