"""Cross-check the reported target displacements and extract raw event provenance."""
import csv
import json
import os
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def center(row):
    t = np.asarray(row['w2c_xyzw'][:3], dtype=np.float64)
    q = np.asarray(row['w2c_xyzw'][3:], dtype=np.float64)
    q /= np.linalg.norm(q)
    v, w = -q[:3], q[-1]
    return -(t + 2 * np.cross(v, np.cross(v, t) + w*t))


def select(d, rid):
    if d['type'] == 'export_matrix':
        return np.asarray(d['c2w'])[rid-1,:3,3]
    slots = d.get('rows', [d.get('row')])
    matches = [s for s in slots if s and s['rgb_id'] == rid]
    assert len(matches) == 1, (d['event'], rid, len(matches))
    return center(matches[0])


def main():
    evd = ROOT/'evidence'
    doc = json.loads((evd/'TASK003_RUNTIME_EVALUATION.json').read_text(encoding='utf-8'))
    scale = doc['sim3_alignment']['scale']
    align_r = np.asarray(doc['sim3_alignment']['R'])
    with (ROOT/'TASK003_VAL007_INTERVAL_ANALYSIS.csv').open(encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['status'] == 'OBSERVED']
    with np.load(doc['gt_path'], allow_pickle=False) as gg:
        poses = gg['c2w']
    wanted = {int(r[k]) for r in rows for k in ('first_event','last_event')}
    targets, series, brackets = {}, [], {}
    trace = ROOT/'remote/capture/observer.jsonl'
    with trace.open('rb') as f:
        for line in f:
            d = json.loads(line)
            i = d['event']
            if i in wanted:
                targets[i] = d
            if d['type'] == 'filler_interpolated':
                for r, (left, right) in zip(d['rows'],d['bracket_rows']):
                    if r['rgb_id'] in {301,309,312,325,328,353}:
                        brackets[r['rgb_id']] = dict(event=i, filler_batch=d['filler_batch'], anchor_rgb_ids=[left['rgb_id'],right['rgb_id']])
            elif d['type'] == 'ba_after_native' and d['stage'].startswith('frontend_local'):
                p = {row['rgb_id']: center(row) for row in d['rows'] if row['rgb_id'] in (312,328)}
                if len(p) == 2:
                    a, b = (312,328)
                    g = poses[b-1,:3,3] - poses[a-1,:3,3]
                    vec = p[b]-p[a]
                    series.append(dict(event=i, stage=d['stage'], trigger_rgb_id=d['trigger_rgb_id'], ba_id=d['ba_id'],
                        landmarks_image_ids=[a,b], length_ratio=float(scale*np.linalg.norm(vec)/np.linalg.norm(g)),
                        world_vector_error_game_units=float(np.linalg.norm(scale*(align_r@vec)-g)),
                        sampled_disparity_negative=d['disparity']['negative'], sampled_disparity_total=d['disparity']['n'],
                        sampled_uncertainty_median=d['uncertainty']['median']))
    cross = []
    for row in rows:
        a,b = [int(row[k]) for k in ('first_rgb','last_rgb')]
        i,j = [int(row[k]) for k in ('first_event','last_event')]
        v = select(targets[j], b) - select(targets[i], a)
        g = poses[b-1,:3,3] - poses[a-1,:3,3]
        val = np.linalg.norm(v)
        np.testing.assert_allclose(val, float(row['length_est_native_units']), atol=2e-6, rtol=0)
        np.testing.assert_allclose(scale*val/np.linalg.norm(g), float(row['length_ratio']), atol=2e-6, rtol=0)
        cross.append(dict(pair=[a,b], stage=row['stage'], events=[i,j],
            world_vector_error_game_units=float(np.linalg.norm(scale*(align_r@v)-g))))
    initials = {str(i): {k: targets[i].get(k) for k in ('trigger_rgb_id','native_iterations_requested','t0','t1','metric_depth_branch_active','metric_depth_positive_support','source_uba','update_u','disparity','uncertainty','sample_grid_step')}
                for i in (2600,2601)}
    assert brackets[309]['anchor_rgb_ids'] == [305,312] and brackets[325]['anchor_rgb_ids'] == [312,328]
    with (evd/'TASK003_TARGET_EVENT_CROSSCHECK.json').open('x', encoding='utf-8') as f:
        json.dump(dict(status='PASS', method='Independent quaternion-vector C2W inversion; same declared full sequence Sim3',
                       rows_checked=len(cross), crosscheck=cross, filler_brackets=brackets,
                       first_colocated_local_call_sample=initials, mode='CPU only'),f,indent=2,allow_nan=False)
    with (ROOT/'TASK003_312_328_LOCAL_BA_TIMELINE.csv').open('x', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(series[0])); w.writeheader(); w.writerows(series)
    print(f'PASS: {len(cross)} interval rows independently verified; {len(series)} local BA returns for 312 to 328.')
    print('First shared local BA, first call below 20% on this descriptive curve, last local BA:')
    print(series[0], next(r for r in series if r['length_ratio'] < .2), series[-1], sep='\n')


if __name__ == '__main__':
    main()
