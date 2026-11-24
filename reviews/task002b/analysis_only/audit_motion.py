"""Recompute locked R2 motion metrics from the original local GT and exports."""

import importlib
import json
import math
import sys
import time
from collections import defaultdict
from zipfile import ZipFile

from audit_common import (COMMITS, EVAL_SHA, INPUT_PRECHECK, OFFSETS, R1, R2,
                          VIRTUAL, ZIP, ZIP_SHA, cpu_guard, digest, exact_member, load_contract,
                          read_csv, require, save_csv, save_json, sha, verify_package)

cpu_guard()
import numpy as np
import scipy
import yaml

MODELS = ('DROID-SLAM', 'DROID-W')
CASE = 'val_007_full_00001-00487'
CASE_PAIRS = ((309, 325), (301, 353))
COMPARE_METRICS = ('translation_rpe_sim3', 'translation_rpe_unscaled', 'rotation_rpe_deg')
EXTRA_OFFSETS = (16, 52)
TOL = 1e-7


def check_reproduction(found, recorded, topic, deltas):
    if found is None:
        require(recorded == '', f'missing value does not reproduce: {topic}')
        return
    previous = float(recorded)
    diff = abs(float(found) - previous)
    require(np.isclose(found, previous, atol=TOL, rtol=TOL), f'does not reproduce: {topic}: {found} vs {recorded}')
    deltas.append(diff)


def assert_close(f, g, description, atol=1e-10):
    require(np.allclose(f, g, atol=atol, rtol=0), description)


def prepare_evaluator(z):
    path = R2 / 'pipeline/offline_evaluation.py'
    require(sha(exact_member(z, 'pipeline/offline_evaluation.py')) == EVAL_SHA, 'offline_evaluation.py SHA mismatch')
    for name in ('transfer_common.py', 'validate_smoke.py'):
        exact_member(z, f'pipeline/{name}')
    sys.path.insert(0, str(path.parent))
    locked = importlib.import_module('offline_evaluation')
    loaders = importlib.import_module('validate_smoke')
    require(locked.__file__ == str(path) and locked.OFFSETS == OFFSETS
            and locked.ALIGNMENT_STAMP == 'VIPER_R1_SEGMENT_METRICS_V1', 'evaluator import identity')
    locked.selfcheck()
    return locked, loaders


def idx_rows(rows, key):
    out = {r[key]: r for r in rows}
    require(len(out) == len(rows), f'duplicate {key} rows')
    return out


def gt_checks(r, gt_hashes, loaders, ids):
    path = R1 / 'offline_gt' / f'{r["sequence"]}.npz'
    require(gt_hashes[r['sequence']] == r['gt_sha256'], 'GT hash disagreement across locks')
    truth = loaders.truth_for(r['sequence'], ids, gt_hashes)
    rmat = truth[:, :3, :3]
    ortho = float(np.max(np.abs(rmat.transpose(0, 2, 1) @ rmat - np.eye(3))))
    det = float(np.max(np.abs(np.linalg.det(rmat) - 1.0)))
    homogeneous = float(np.max(np.abs(truth[:, 3] - [0, 0, 0, 1])))
    require(max(ortho, det, homogeneous) <= 2e-3, 'GT is not homogeneous SO(3)')
    return truth, dict(gt_path=str(path), gt_sha256=gt_hashes[r['sequence']],
                       gt_first_camera_frame=int(ids[0]-1), gt_last_camera_frame=int(ids[-1]-1),
                       gt_max_rotation_orthogonality_error=ortho, gt_max_det_error=det,
                       gt_max_last_row_error=homogeneous)


def kbits(v):
    return np.asarray(v, np.float32).view(np.uint32).tolist()


def verify_input(z, r, plan, historical, slam, wild, slam_dir):
    sid, seq, branch = r['id'], r['sequence'], r['branch']
    count, first, last = (int(r[k]) for k in ('frames', 'first', 'last'))
    wdir = f'wild_reference/{sid}'
    ids = list(range(first, last+1))
    expect_k = json.loads(r['actual_loader_k'])
    jsha = r['input_manifest_sha256']
    b = exact_member(z, f'manifests/{sid}.json')
    require(sha(b) == jsha, 'segment JPEG manifest SHA')
    m = json.loads(b)
    require(m['id'] == sid and m['sequence'] == seq and m['environment'] == r['environment']
            and m['branch'] == branch and m['stride'] == 1 and m['fps_nominal'] == 15
            and m['raw_wh'] == [1920, 1080] and m['out_wh'] == [640, 360]
            and count == len(ids) == len(m['frames']) and [f['rgb_id'] for f in m['frames']] == ids
            and all(f['file'] == f'{f["rgb_id"]:05d}.jpg' and f['bytes'] > 0 and len(f['sha256']) == 64
                    for f in m['frames']), 'manifest geometry or frame identities')
    require(all(plan[k] == v for k, v in dict(id=sid, sequence=seq, branch=branch, environment=r['environment'],
                first=first, last=last, frames=count, input_manifest_sha256=jsha, actual_loader_k=expect_k,
                wild_rgb_tensor_sha256=r['wild_rgb_tensor_sha256']).items()), 'formal worklist disagreement')
    for rec in (slam, wild):
        require(rec['segment'] == sid and rec['sequence'] == seq and rec['environment'] == r['environment']
                and rec['calibration_branch'] == branch and rec['input_frames'] == count
                and rec['stride'] == 1 and rec['input_manifest_sha256'] == jsha,
                'attempt input identification mismatch')
    cfg = json.loads(exact_member(z, f'{slam_dir}/model_config.json'))
    rec = json.loads(exact_member(z, f'{slam_dir}/input_receipt.json'))
    wcfg = json.loads(exact_member(z, f'{wdir}/model_input.json'))
    wraw = json.loads(exact_member(z, f'{wdir}/input_receipt.json'))
    wtrack = json.loads(exact_member(z, f'{wdir}/tracking_child_ok.json'))
    wyaml = exact_member(z, f'{wdir}/native_config.yaml')
    require(sha(wyaml) == r['wild_config_sha256'], 'frozen DROID-W config hash')
    y = yaml.safe_load(wyaml)
    cam = y['cam']
    require((cam['W'], cam['H'], cam['W_out'], cam['H_out'], cam['W_edge'], cam['H_edge']) == (1920, 1080, 640, 360, 0, 0)
            and cam.get('distortion') is None and y['dataset'] == 'youtube', 'unexpected DROID-W image settings')
    require(cfg['input_rgb_ids'] == wcfg['rgb_ids'] == ids and cfg['image_size'] == [360, 640]
            and wcfg['size'] == [640, 360] and wcfg['branch'] == branch
            and cfg['stride'] == wcfg['stride'] == 1 and cfg['supplied_pose_rows'] == wcfg['pose_inputs'] == 0
            and cfg['input_manifest_sha256'] == wcfg['manifest_sha256'] == wraw['input_manifest_sha256'] == jsha
            and wraw['frames'] == count, 'effective loader or pose isolation mismatch')
    neq = {key for key in historical.keys() | rec.keys() if historical.get(key) != rec.get(key)}
    require(neq <= {'seconds'} and rec['status'] == 'PASS' and rec['frames'] == count
            and rec['first_rgb_id'] == first and rec['last_rgb_id'] == last
            and rec['input_manifest_sha256'] == jsha and rec['branch'] == branch
            and rec['historic_tensor_match'] is True and rec['opencv'] == '4.8.1'
            and rec['original_jpeg_bytes'] == sum(f['bytes'] for f in m['frames']), 'preflight receipt mismatch')
    # Equality here is IEEE float32 equality, including the rounding of focal values.
    bits = kbits(expect_k)
    require(kbits(rec['K']) == kbits(cfg['effective_k']) == kbits(wcfg['actual_loader_k']) == bits,
            'actual K differs between loaders')
    kconf = np.array([cam[k] for k in ('fx', 'fy', 'cx', 'cy')])
    kout = np.array(m['output_k'])
    assert_close(kconf, 3*kout, 'loader precompensated K')
    k_cpu = kconf.astype(np.float32) * np.float32(1/3)
    require(kbits(k_cpu) == bits, 'float32 K reconstructed from W runner config does not reproduce')
    k8 = k_cpu / np.float32(8)
    require(slam['tracked_bgr_sha256'] == slam['filler_bgr_sha256'] == rec['bgr_uint8_hwc_sha256'],
            'DROID-SLAM tracking or filler BGR hash mismatches preflight')
    require(rec['rgb_float32_chw_sha256'] == wild['scaled_rgb_tensor_sha256'] == wtrack['scaled_rgb_tensor_sha256']
            == r['wild_rgb_tensor_sha256'] and wtrack['read_frames'] == wtrack['filler_frames']
            == wild['read_frames'] == wild['filler_frames'] == count, 'DROID-W tracking SHA or loader counts mismatch')
    source = np.array([f['source_k'] for f in m['frames']]) if branch == VIRTUAL else np.array([m['fixed_source_k']])
    require(np.isfinite(source).all() and (source[:, :2] > 0).all(), 'unusable source K')
    return dict(input_manifest_sha256=jsha, jpeg_id_contiguous=True, rgb_frames=count,
                original_jpeg_bytes=rec['original_jpeg_bytes'], pose_inputs_slam=0, pose_inputs_wild=0,
                preflight_vs_actual_receipt_fields_different=';'.join(sorted(neq)),
                slam_tracking_bgr_sha256=slam['tracked_bgr_sha256'], slam_filler_bgr_sha256=slam['filler_bgr_sha256'],
                wild_tracking_rgb_f32_sha256=wild['scaled_rgb_tensor_sha256'], wild_filler_frames=wtrack['filler_frames'],
                wild_filler_tensor_sha256=None, loader_k_f32_bitwise_equal=True,
                effective_k_640x360=json.dumps(k_cpu.tolist()), k_div8_f32=json.dumps(k8.tolist()),
                intrinsic_audit_units='px', branch_source_k_min=json.dumps(source.min(0).tolist()),
                branch_source_k_max=json.dumps(source.max(0).tolist()),
                nominal_output_k=json.dumps(kout.tolist()),
                max_f32_minus_nominal_k_px=float(np.max(np.abs(k_cpu-kout))))


def check_trajectory(z, loaders, rel, rec, ids, expected):
    require(rec['status'] == 'COMPLETE' and rec['exit_code'] == 0 and rec['trajectory_sha256'] == expected,
            f'noncomplete or inconsistent trajectory receipt: {rel}')
    payload = exact_member(z, f'{rel}/trajectory.npz')
    require(sha(payload) == expected, f'trajectory SHA mismatch: {rel}')
    pred, valid, keys = loaders.checked_trajectory(R2 / rel / 'trajectory.npz', expected, ids)
    require(len(keys) == rec['keyframes'] and len(ids) == rec['poses_exported'] and int(valid.sum()) == rec['valid_poses'],
            f'export coverage differs from receipt: {rel}')
    qerr = float(np.max(np.abs(np.linalg.norm(pred[:, 3:], axis=1) - 1)))
    return pred, valid, keys, qerr


def compression(locked, truth, ids, masks, preds, scales, offsets):
    # Descriptive endpoints only. The frozen RPE computation is used separately.
    pg = truth[:, :3, 3]
    for off in offsets:
        i, j = locked.pairs(ids, off, masks[0] & masks[1])
        d = np.linalg.norm(pg[j] - pg[i], axis=1)
        dpass = d > locked.TRUTH_MIN_STEP
        median = float(np.median(d[dpass])) if np.any(dpass) else None
        gfilter = dpass & (d >= .5*median) if median is not None else dpass
        i, j, d = i[gfilter], j[gfilter], d[gfilter]
        ratios = [np.linalg.norm(p[j, :3] - p[i, :3], axis=1) * s / d for p, s in zip(preds, scales)]
        if not len(i):
            yield dict(offset=off, eligible_motion_pairs=0, gt_step_screen_game_units=median,
                       suppressed_wild_pairs=0, suppressed_slam_pairs=0, both_suppressed_pairs=0,
                       wild_specific_pairs=0, wild_specific_runs_ge5=0, longest_wild_specific_run=0)
            continue
        a, b = ratios
        cutoff_a, cutoff_b = a < .5, b < .5
        w_only_mask = cutoff_b & (a >= .8) & (a <= 1.2)
        w_only = i[w_only_mask]
        blocks = np.split(w_only, np.flatnonzero(np.diff(w_only) > 1)+1) if len(w_only) else []
        longest = max(map(len, blocks), default=0)
        first = next((k for k in blocks if len(k) == longest), None)
        k = int(np.argmin(b))
        yield dict(offset=off, eligible_motion_pairs=len(i), gt_step_screen_game_units=.5*median,
                   slam_median_step_ratio=float(np.median(a)), wild_median_step_ratio=float(np.median(b)),
                   suppressed_wild_pairs=int(cutoff_b.sum()), suppressed_slam_pairs=int(cutoff_a.sum()),
                   both_suppressed_pairs=int(np.count_nonzero(cutoff_a & cutoff_b)),
                   wild_specific_pairs=int(w_only_mask.sum()), wild_specific_runs_ge5=sum(len(k) >= 5 for k in blocks),
                   longest_wild_specific_run=longest,
                   strongest_wild_pair_start_rgb=int(ids[i[k]]), strongest_wild_pair_end_rgb=int(ids[j[k]]),
                   strongest_wild_pair_wild_ratio=float(b[k]), strongest_wild_pair_slam_ratio=float(a[k]),
                   longest_wild_specific_run_start_rgb=None if first is None else int(ids[first[0]]),
                   longest_wild_specific_run_end_rgb=None if first is None else int(ids[first[-1] + off]))


def case_pair(locked, sid, truth, ids, pred, mask, score, aligned, name, key_ids, first, last):
    i, j = int(np.where(ids == first)[0][0]), int(np.where(ids == last)[0][0])
    ii, jj = locked.pairs(ids, last-first, mask)
    require(np.any((ii == i) & (jj == j)), f'val_007 noncontiguous evidence interval: {first}->{last}')
    ep, gp = pred[:, :3], truth[:, :3, 3]
    a, g = aligned['sim3'][j]-aligned['sim3'][i], gp[j]-gp[i]
    pn, gn = float(np.linalg.norm(a)), float(np.linalg.norm(g))
    direction = math.degrees(math.acos(float(np.clip(a@g / (pn*gn), -1, 1))))
    er = locked.Rotation.from_quat(pred[:, 3:]).as_matrix()
    t_pred, r_pred = locked.rel_pose(ep, er, np.array([i]), np.array([j]))
    t_gt, r_gt = locked.rel_pose(gp, truth[:, :3, :3], np.array([i]), np.array([j]))
    rot = float(np.degrees(locked.Rotation.from_matrix(r_gt.transpose(0, 2, 1) @ r_pred).magnitude())[0])
    return dict(segment=sid, model=name, first_rgb=first, last_rgb=last, first_camera_frame=first-1,
                last_camera_frame=last-1, offset=last-first, official_rpe_offset=False,
                interval_frames=last-first+1, all_interval_poses_valid=True,
                native_displacement=float(np.linalg.norm(ep[j]-ep[i])), scale_est_to_gt=score['scale_est_to_gt'],
                scaled_displacement_game_units=pn, gt_displacement_game_units=gn, scaled_to_gt_ratio=pn/gn,
                displacement_error_game_units=float(np.linalg.norm(a-g)), direction_error_deg=direction,
                official_rpe_convention_translation_one_pair=locked.rmse(score['scale_est_to_gt']*t_pred-t_gt),
                relative_camera_rotation_error_deg=rot, first_is_keyframe=bool(first in key_ids),
                last_is_keyframe=bool(last in key_ids))


def audit():
    t0 = time.monotonic()
    count = verify_package()
    print(f'Original R2 ZIP: SHA-256 and {count} member CRC checks PASS', flush=True)
    all_rows, integrity, input_rows, anomaly_rows, cases, issues = [], [], [], [], [], []
    stats_deltas, rpe_deltas, case_deltas = [], [], []
    with ZipFile(ZIP) as z:
        lock, manifest = load_contract(z)
        ev, loaders = prepare_evaluator(z)
        for key, expected in lock['evaluation']['plan_sha256'].items():
            require(digest(R1 / key) == expected, f'original R1 plan SHA mismatch: {key}')
        worklist = exact_member(z, INPUT_PRECHECK)
        require(sha(worklist) == lock['rgb_worklist_sha256'], 'worklist SHA mismatch')
        work = idx_rows(json.loads(worklist)['segments'], 'id')
        queue_doc = json.loads(exact_member(z, 'evidence/FORMAL_QUEUE_STATUS.json'))
        require(queue_doc['input_sha256'] == sha(worklist) and queue_doc['phase'] == 'finished', 'queue identity mismatch')
        queue = idx_rows(queue_doc['results'], 'segment')
        preflight = idx_rows(json.loads(exact_member(z, 'evidence/REMOTE_PIXEL_PAIRING.json'))['results'], 'segment')
        gt_hashes = json.loads(exact_member(z, 'evidence/R1_PRESERVATION_AND_SCORE_CHECK.json'))['gt_file_sha256']
        compare_file = 'evaluation/PAIRED_SEGMENT_COMPARISON.csv'
        exact_member(z, compare_file)
        archived_scores = idx_rows(read_csv(R2 / compare_file), 'segment')
        historical_file = 'evaluation/MATCHED_RPE_BY_SCOPE.csv'
        exact_member(z, historical_file)
        old_rows = {(r['segment'], r['model'], r['scope'], int(r['delta_rgb_frames'])): r
                    for r in read_csv(R2 / historical_file)}
        case_file = 'evaluation/VAL007_LOCAL_DISPLACEMENT.csv'
        exact_member(z, case_file)
        old_cases = {(r['model'], int(r['first_rgb']), int(r['last_rgb'])): r for r in read_csv(R2 / case_file)}
        require({r['id'] for r in manifest} == set(work) == set(queue) == set(preflight) == set(archived_scores),
                'R2 segment sets differ')
        seq_ids = defaultdict(list)
        for row in manifest:
            sid, seq, branch = row['id'], row['sequence'], row['branch']
            ids = np.arange(int(row['first']), int(row['last'])+1)
            seq_ids[seq].extend(ids.tolist())
            meta = dict(segment=sid, sequence=seq, environment=row['environment'], calibration_branch=branch,
                        first_rgb=int(ids[0]), last_rgb=int(ids[-1]), input_frames=len(ids))
            sr, wr = f'results/{sid}/attempt_001', f'wild_reference/{sid}'
            stage = 'GT'
            try:
                truth, truth_info = gt_checks(row, gt_hashes, loaders, ids)
                stage = 'receipts and inputs'
                srec = json.loads(exact_member(z, f'{sr}/attempt.json'))
                wrec = json.loads(exact_member(z, f'{wr}/attempt.json'))
                require(srec == queue[sid] and srec['launched'] is True and srec['upstream_commit'] == COMMITS[MODELS[0]]
                        and wrec['upstream_commit'] == COMMITS[MODELS[1]], 'attempt queue or commit mismatch')
                require(srec['attempt'] == sr, 'unexpected original DROID-SLAM trajectory path')
                mr = json.loads(exact_member(z, f'{sr}/model_result.json'))
                require(all(srec[k] == v for k, v in mr.items()), 'DROID-SLAM final record mismatches terminal receipt')
                input_info = verify_input(z, row, work[sid], preflight[sid], srec, wrec, sr)
                input_rows.append({**meta, **input_info})
                stage = 'trajectory export'
                tr = [check_trajectory(z, loaders, sr, srec, ids, mr['trajectory_sha256']),
                      check_trajectory(z, loaders, wr, wrec, ids, row['wild_trajectory_sha256'])]
                stage = 'frozen evaluator'
                # Compute all 16 locked scope/offset rows per model. Export accounting remains separate.
                eval_result = [ev.metrics(p, truth, ids, v) for p, v, _, _ in tr]
                masks = [x[1] for x in tr]
                for k, name in enumerate(MODELS):
                    p, valid, keys, qerr = tr[k]
                    rec, scope_scores, aligned = eval_result[k]
                    prefix = ('slam_', 'wild_')[k]
                    for field in ('ate_sim3_game_units', 'ate_se3_game_units', 'ate_sim3_path_pct', 'scale_est_to_gt'):
                        check_reproduction(rec[field], archived_scores[sid][prefix+field], f'{sid} {name} {field}', stats_deltas)
                    cov = dict(model=name, export_completion=True, exported_pose_count=len(p), valid_pose_count=int(valid.sum()),
                               missing_pose_count=len(ids)-len(p), invalid_pose_count=int((~valid).sum()),
                               exported_pose_coverage=len(p)/len(ids), valid_pose_coverage=float(valid.mean()),
                               keyframe_count=len(keys), max_quaternion_norm_error=qerr)
                    integrity.append({**meta, **truth_info, **cov, 'trajectory_sha256': (srec, wrec)[k]['trajectory_sha256'],
                                      'trajectory_path': str(R2 / (sr, wr)[k] / 'trajectory.npz')})
                    for rs in scope_scores:
                        scope, off = rs['scope'], rs['delta_rgb_frames']
                        archived = old_rows[(sid, name, scope, off)]
                        for field in ('motion_pairs', *COMPARE_METRICS):
                            check_reproduction(rs[field], archived[field], f'{sid} {name} {scope} {off} {field}', rpe_deltas)
                        scope_mask = np.ones(len(ids), bool)
                        if scope != 'full':
                            scope_mask[:] = False
                            scope_mask[np.array_split(np.arange(len(ids)), 3)[('early', 'middle', 'late').index(scope)]] = True
                        eligible = len(ev.pairs(ids, off, scope_mask)[0])
                        common_mask = scope_mask & masks[0] & masks[1]
                        common_n = len(ev.pairs(ids, off, common_mask)[0])
                        valid_n = rs['motion_pairs']
                        # The original R2 loader requires full validity. No pair-weight shift is allowed here.
                        require(common_n == valid_n == eligible, 'not all sealed trajectory pairs valid')
                        all_rows.append(dict(meta, **cov, scope=scope, offset=off, nominal_seconds=rs['delta_nominal_s'],
                                             translation_rpe=rs['translation_rpe_sim3'], rotation_rpe=rs['rotation_rpe_deg'],
                                             translation_rpe_sim3_game_units=rs['translation_rpe_sim3'],
                                             translation_rpe_unscaled_native_comparison=rs['translation_rpe_unscaled'],
                                             rotation_rpe_deg=rs['rotation_rpe_deg'],
                                             valid_frames_in_scope=int(np.count_nonzero(scope_mask & valid)),
                                             expected_pair_count=eligible, valid_pair_count=valid_n,
                                             invalid_pair_count=eligible-valid_n, common_valid_pair_count=common_n,
                                             coverage_ratio=valid_n/eligible if eligible else None,
                                             median_scaled_displacement_ratio=rs['local_translation_ratio_scaled_median'],
                                             nonzero_gt_pairs=rs['nonzero_gt_pairs'], **rec))
                    if sid == CASE:
                        for start, end in CASE_PAIRS:
                            item = case_pair(ev, sid, truth, ids, p, valid, rec, aligned, name, keys, start, end)
                            previous = old_cases[(name, start, end)]
                            for f in ('scaled_displacement_game_units', 'gt_displacement_game_units', 'scaled_to_gt_ratio',
                                      'displacement_error_game_units', 'direction_error_deg'):
                                check_reproduction(item[f], previous[f], f'{sid} {name} {start}-{end} {f}', case_deltas)
                            cases.append(item)
                stage = 'paired compression screen'
                for an in compression(ev, truth, ids, masks, [x[0] for x in tr],
                                      [x[0]['scale_est_to_gt'] for x in eval_result], (*OFFSETS, *EXTRA_OFFSETS)):
                    anomaly_rows.append(dict(meta, **an, protocol_rpe_offset=an['offset'] in OFFSETS))
            except (OSError, ValueError, KeyError, AssertionError, yaml.YAMLError) as e:
                issues.append(dict(segment=sid, sequence=seq, stage=stage, error=str(e)))
                all_rows[:] = [x for x in all_rows if x['segment'] != sid]
                anomaly_rows[:] = [x for x in anomaly_rows if x['segment'] != sid]
                cases[:] = [x for x in cases if x['segment'] != sid]
                print(f'BLOCKED {sid} ({stage}): {e}', file=sys.stderr, flush=True)
            if len(integrity) and len(integrity) % 46 == 0:
                print(f'{len(integrity)} model exports verified; {len(all_rows)} scope/offset rows reproduced', flush=True)
        for seq, used in seq_ids.items():
            require(sorted(used) == list(range(1, len(used)+1)) and len(used) == len(set(used)), f'sequence gaps or overlap: {seq}')
            # Validate identity coverage for the full sequence, without joining its estimated poses.
            with np.load(R1/'offline_gt'/f'{seq}.npz', allow_pickle=False) as data:
                require(np.array_equal(data['rgb_ids'], np.arange(1, len(used)+1)), f'GT sequence lengths or IDs: {seq}')
        summary = dict(status='PASS' if not issues else 'PARTIAL', protocol=lock['protocol'], inputs=[str(R2), str(R1)],
                       pinned_commits=COMMITS, r2_zip_path=str(ZIP), r2_zip_sha256=ZIP_SHA, r2_zip_crc='PASS',
                       r2_zip_member_count=count, frozen_manifest_sha256=lock['manifest_sha256'],
                       metric_version=ev.ALIGNMENT_STAMP, evaluation_source_sha256=EVAL_SHA,
                       evaluated_sequences=len({r['sequence'] for r in all_rows}), planned_sequences=len(seq_ids),
                       evaluated_segments=len({r['segment'] for r in all_rows}),
                       planned_segments=len(manifest), expected_input_frames=lock['frames'],
                       input_receipts_pass=len(input_rows), trajectory_exports_verified=len(integrity),
                       exported_poses={m:sum(r['valid_pose_count'] for r in integrity if r['model'] == m) for m in MODELS},
                       keyframes={m:sum(r['keyframe_count'] for r in integrity if r['model'] == m) for m in MODELS},
                       rpe_scope_offset_rows=len(all_rows), official_historical_rpe_rows=len(old_rows),
                       historical_rpe_comparison_cells=len(rpe_deltas), max_rpe_cell_absolute_delta=max(rpe_deltas, default=None),
                       historic_ate_and_scale_comparison_cells=len(stats_deltas), max_ate_scale_cell_absolute_delta=max(stats_deltas, default=None),
                       val007_reference_comparison_cells=len(case_deltas), max_case_absolute_delta=max(case_deltas, default=None),
                       rtol_atol=TOL, scipy=scipy.__version__, numpy=np.__version__, python=sys.version,
                       direct_tracking_success_rate=None, exceptions=issues, wall_seconds=time.monotonic()-t0)
    save_csv('R2_TRAJECTORY_AND_GT_INTEGRITY.csv', integrity, None if integrity else ['segment','model'])
    save_csv('R2_RUNTIME_INPUT_RECEIPT_PARITY.csv', input_rows, None if input_rows else ['segment'])
    save_csv('R2_RPE_PER_SEGMENT.csv', all_rows, None if all_rows else ['segment','model','scope','offset'])
    save_csv('R2_LOCAL_TRANSLATION_COMPRESSION_SCREEN.csv', anomaly_rows, None if anomaly_rows else ['segment','offset'])
    save_csv('R2_VAL007_LOCAL_INTERVAL_VERIFICATION.csv', cases, None if cases else ['segment','model','first_rgb','last_rgb'])
    save_json('TASK002B_FROZEN_EVIDENCE_AUDIT.json', summary)
    print(f'R2 {summary["status"]}: {summary["evaluated_segments"]}/92 evaluated segments; '
          f'{len(all_rows)} RPE rows; {len(issues)} evidence exceptions; {summary["wall_seconds"]:.1f}s', flush=True)
    return int(bool(issues))


if __name__ == '__main__':
    raise SystemExit(audit())
