"""Verify publication values, coverage and frozen identities without rerunning metrics."""
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
FIXED = 'FIXED_K_NATIVE_RESIZE'
VIRTUAL = 'VIRTUAL_K_DIRECT_REMAP'
ENVS = {'Day', 'Sunset', 'Rain', 'Snow', 'Night', 'ALL_ENVIRONMENTS'}
ALL = 'ALL_ENVIRONMENTS'
CLASSES = {'K': 'KEYFRAME', 'F': 'FILLED_FRAME'}
OFFSETS = (1, 15, 60, 150)
MODELS = ('DROID-SLAM', 'DROID-W')


def rows(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def md(name):
    return (ROOT / name).read_text(encoding='utf-8-sig')


def one(items, **fields):
    found = [row for row in items if all(row.get(k) == str(v) for k, v in fields.items())]
    assert len(found) == 1, (fields, len(found))
    return found[0]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def integer(text):
    return int(text.replace(',', '').rstrip('*'))


def displayed_pair(text, row):
    lhs, rhs = text.split(' / ')
    for observed, side in ((lhs, 'left'), (rhs, 'right')):
        actual = float(row[f'{side}_seq_rmse_median'])
        assert math.isclose(float(observed), actual, rel_tol=0, abs_tol=0.0005), (text, row)


def report_checks():
    pose = [r for r in rows('POSE_ERROR_ENVIRONMENT_PAIRED.csv')
            if r['population'] == 'MATCHED' and r['temporal_third'] == 'all']
    paired = [r for r in rows('RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv')
              if r['contrast'] == 'W_MINUS_SLAM_MATCHED_RGB' and r['offset'] == '60']
    recurrence = [r for r in rows('COMPRESSION_RECURRENCE_BY_ENVIRONMENT.csv')
                  if r['wild_type'] == 'ALL' and r['offset'] == '60']
    members = rows('KEYFRAME_MEMBERSHIP_BY_ENVIRONMENT.csv')
    verified = Counter()
    for line in md('FIVE_ENVIRONMENT_KEYFRAME_FILLER_REPORT.md').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.split('|')[1:-1]]
        name = ALL if cells[0] == '主组合计' else cells[0]
        if len(cells) == 8 and name in ENVS:
            rec = one(members, calibration_branch=FIXED, environment=name)
            assert tuple(map(integer, cells[1].split(' / '))) == (int(rec['sequences']), int(rec['segments']))
            for j, cls in ((2, 'KEYFRAME'), (5, 'FILLED_FRAME')):
                data = [one(pose, calibration_branch=FIXED, environment=name, frame_type=cls, metric=unit)
                        for unit in ('translation', 'rotation')]
                assert integer(cells[j]) == int(data[0]['left_valid_count']) == int(data[0]['right_valid_count'])
                assert int(data[0]['paired_sequences']) == int(rec['sequences'])
                for cell, r in zip(cells[j+1:j+3], data):
                    displayed_pair(cell, r)
            verified['pose_rows'] += 1
        elif (len(cells) == 6 and name in ENVS) or (len(cells) == 5 and '→' in name):
            branch = FIXED if len(cells) == 6 else VIRTUAL
            env = name if branch == FIXED else 'Day'
            kind, n, count, translation, rotation = cells[-5:]
            a, b = kind.split('→')
            cls = f'{CLASSES[a]}->{CLASSES[b]}'
            for cell, unit in ((translation, 'translation'), (rotation, 'rotation')):
                r = one(paired, calibration_branch=branch, environment=env, slam_type=cls, wild_type=cls, metric=unit)
                assert integer(n) == int(r['paired_sequences'])
                assert integer(count) == int(r['left_valid_count']) == int(r['right_valid_count'])
                displayed_pair(cell, r)
            verified[branch] += 1
        elif len(cells) == 3 and name in ENVS:
            rec = one(recurrence, calibration_branch=FIXED, environment=name)
            assert tuple(map(integer, cells[1].split(' / '))) == (int(rec['sequences_with_hits']), int(rec['sequences_with_screened_pairs']))
            assert tuple(map(integer, cells[2].split(' / '))) == (int(rec['hit_pairs']), int(rec['screened_pairs']))
            verified['screen_rows'] += 1
    assert dict(verified) == {'pose_rows': 6, FIXED: 24, VIRTUAL: 4, 'screen_rows': 6}, verified
    return dict(verified)


def coverage_checks():
    ids = rows('KEYFRAME_ID_AUDIT.csv')
    assert len(ids) == len({(r['segment'], r['model']) for r in ids}) == 184
    assert len({r['segment'] for r in ids}) == 92
    assert all(int(r['missing_count']) == int(r['invalid_count']) == 0 and r['input_frames'] == r['valid_count']
               and r['recorded_pre_final_ba_anchor_pose_count'] == '0' for r in ids)
    expected = {(m, FIXED): (82, 45, 43412) for m in MODELS} | {(m, VIRTUAL): (10, 2, 6403) for m in MODELS}
    for (model, branch), (nseg, nseq, nframe) in expected.items():
        group = [r for r in ids if r['model'] == model and r['calibration_branch'] == branch]
        assert (len(group), len({r['sequence'] for r in group}), sum(int(r['valid_count']) for r in group)) == (
            nseg, nseq, nframe)
    indexes = rows('RPE_PAIR_SEGMENT_INDEX.csv')
    assert len(indexes) == len({r['segment_index'] for r in indexes}) == 92
    p = one(indexes, segment='val_007_full_00001-00487')
    for model, side in zip(MODELS, ('slam', 'wild')):
        row = one(ids, segment=p['segment'], model=model)
        assert row['trajectory_sha256'] == p[f'{side}_trajectory_sha256']
    own = [r for r in rows('RPE_BY_ENDPOINT_TYPE.csv') if r['population'] == 'OWN']
    assert len(own) == 184 * 4 * len(OFFSETS)
    for (model, branch), (nseg, _, nframe) in expected.items():
        for off in OFFSETS:
            g = [r for r in own if (r['model'], r['calibration_branch'], int(r['offset'])) == (model, branch, off)]
            assert len(g) == 4 * nseg
            assert all(r['valid_count'] == r['expected_count'] and r['invalid_or_missing_count'] == '0' for r in g)
            assert sum(int(r['valid_count']) for r in g) == nframe - nseg * off
    reconcile = rows('RPE_PARTITION_RECONCILIATION.csv')
    assert len(reconcile) == 736
    assert all(float(r['translation_rmse']) == float(r['translation_rmse_parent']) and
               float(r['rotation_rmse_deg']) == float(r['rotation_rmse_parent']) for r in reconcile)
    return {'verified_exports': len(ids), 'per_model_valid_pose_count': 49815, 'endpoint_partitions': len(reconcile)}


def case_checks():
    ids = rows('KEYFRAME_ID_AUDIT.csv')
    case = 'val_007_full_00001-00487'
    numbers = rows('VAL007_ANCHOR_INTERVALS.csv')
    for model, ratio, kind in (('DROID-SLAM', 1.02165, 'FILLED_FRAME'), ('DROID-W', .02615, 'KEYFRAME')):
        a = one(numbers, model=model, first_rgb=312, last_rgb=328, role='near_325')
        assert a['endpoint_type'] == f'{kind}->{kind}'
        assert a['trajectory_sha256'] == one(ids, segment=case, model=model)['trajectory_sha256']
        assert round(float(a['scaled_displacement_ratio']), 5) == ratio
    c = one(rows('KEYFRAME_CONSECUTIVE_RPE.csv'), segment=case, model='DROID-W', first_rgb=312, last_rgb=328)
    assert c['actual_rgb_gap'] == '16' and c['valid_complete_interval'] == 'True'
    assert round(float(c['translation_rpe_game_units']), 3) == 27.031
    assert round(float(c['rotation_rpe_deg']), 4) == .1083
    cases = rows('VAL007_CASE_INTERVALS.csv')
    assert len(cases) == 4
    for a in cases:
        assert a['formal_offset'] == 'False' and int(a['last_rgb']) - int(a['first_rgb']) in (16, 52)
        assert int(a['first_camera_id']) == int(a['first_rgb']) - 1
        assert int(a['last_camera_id']) == int(a['last_rgb']) - 1
        assert a['trajectory_sha256'] == one(ids, segment=case, model=a['model'])['trajectory_sha256']
    direct = rows('MATCHED_KEYFRAME_ANCHOR_SENSITIVITY.csv')
    x = one(direct, calibration_branch=FIXED, environment=ALL, offset=60, metric='translation',
            contrast='SLAM_DIRECT_BA_MINUS_SLAM_EXPORTED')
    assert (int(x['paired_sequences']), int(x['left_valid_count'])) == (27, 592)
    assert [round(float(x[f'{k}_seq_rmse_median']), 6) for k in ('left','right')] == [1.678867, 1.678958]
    return {'special_intervals': 4, 'primary_anchor_rgb_ids': [312,328], 'direct_anchor_offset60_pairs': 592}


def identity_checks():
    original = rows('evidence/ORIGINAL_EVIDENCE_PRESERVATION.csv')
    assert len(original) == len({r['path'] for r in original}) == 986
    for r in original:
        p = Path(r['path']).resolve(strict=True)
        assert p.is_relative_to(PROJECT) and not p.is_relative_to(ROOT), p
        assert r['unchanged'] == 'True' and p.stat().st_size == int(r['bytes']) and sha(p) == r['sha256'], p
    sources = rows('evidence/SOURCE_PROVENANCE.csv')
    assert len(sources) == 15
    for r in sources:
        p = Path(r['local_path']).resolve(strict=True)
        assert p.is_relative_to(PROJECT) and not p.is_relative_to(ROOT), p
        assert r['status'] == 'MATCH' and p.stat().st_size == int(r['bytes']) and sha(p) == r['sha256'], p
    for stem in ('decompose','aggregate','verify_sources_and_anchors','render_figures'):
        assert md(f'logs/{stem}.exit.txt').strip() == '0'
        assert (ROOT / f'logs/{stem}.stdout.log').stat().st_size > 0
        assert (ROOT / f'logs/{stem}.stderr.log').stat().st_size == 0
    for name in re.findall(r'\]\(([^)]+)\)', md('TASK002B_ADDENDUM_FINAL_REVIEW.md')):
        assert (ROOT / name).is_file(), name
    return {'historical_matches': len(original), 'source_matches': len(sources), 'execution_log_triples': 4}


if __name__ == '__main__':
    print(json.dumps({'status': 'PASS', 'coverage': coverage_checks(), 'case': case_checks(),
                      'five_environment_report': report_checks(), 'identity': identity_checks()}, indent=2))
