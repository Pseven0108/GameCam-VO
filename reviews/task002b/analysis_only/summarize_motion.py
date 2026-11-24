"""Sequence-clustered summaries of locked per-segment outputs; no pose stitching."""

from collections import defaultdict
import math

from audit_common import ENVIRONMENTS, FIXED, OFFSETS, OUT, R2, VIRTUAL, cpu_guard, read_csv, require, save_csv, save_json

cpu_guard()
import numpy as np

MODELS = ('DROID-SLAM', 'DROID-W')
METRICS = ('translation_rpe_sim3_game_units', 'rotation_rpe_deg', 'translation_rpe_unscaled_native_comparison')
BOOTSTRAP_SEED, BOOTSTRAP_DRAWS = 20261122, 10_000


def val(v):
    return float(v) if v not in ('', None) else None


def pooled(rows, key, weight):
    values = [(float(r[key]), int(r[weight])) for r in rows if val(r[key]) is not None and int(r[weight]) > 0]
    total = sum(n for x, n in values)
    return math.sqrt(sum(x*x*n for x, n in values) / total) if total else None


def count(rows, key):
    return sum(int(r[key]) for r in rows)


def descriptive(values):
    v = np.asarray(values, dtype=float)
    return dict(mean=float(v.mean()) if len(v) else None, median=float(np.median(v)) if len(v) else None,
                std=float(v.std(ddof=1)) if len(v) > 1 else None,
                p90=float(np.quantile(v, .90)) if len(v) else None,
                p95=float(np.quantile(v, .95)) if len(v) else None)


def bootstrap_ci(values, indices):
    if indices is None:
        return None, None
    ci = np.quantile(np.mean(np.asarray(values, dtype=float)[indices], axis=1), [.025, .975])
    return float(ci[0]), float(ci[1])


def with_ci(values, rng, indices=None):
    if indices is None and len(values) > 1:
        indices = rng.integers(0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))
    lo, hi = bootstrap_ci(values, indices)
    return dict(**descriptive(values), ci95_low=lo, ci95_high=hi)


def stability(n):
    if n == 0:
        return 'NOT_AVAILABLE'
    if n == 1:
        return 'ONE_SEQUENCE_NO_CI'
    if n < 5:
        return 'VERY_SMALL_N_DESCRIPTIVE'
    if n < 10:
        return 'SMALL_N_EXPLORATORY'
    return 'EXPLORATORY_BOOTSTRAP'


def by_sequence(full):
    groups = defaultdict(list)
    for row in full:
        groups[row['sequence'], row['model'], int(row['offset'])].append(row)
    existing = {r['sequence']: r for r in read_csv(R2 / 'evaluation/PAIRED_SEQUENCE_COMPARISON.csv')}
    results, max_historical_gap = [], 0.
    for (seq, model, off), rows in sorted(groups.items()):
        first = rows[0]
        got = {r['segment'] for r in rows}
        require(len(got) == len(rows), f'duplicate segment rows: {seq}/{model}/{off}')
        n = count(rows, 'expected_pair_count')
        nvalid = count(rows, 'valid_pair_count')
        nframes = count(rows, 'input_frames')
        scores = {m: pooled(rows, m, 'valid_pair_count') for m in METRICS}
        raw_ate = [r['ate_sim3_path_pct'] for r in rows if val(r['ate_sim3_path_pct']) is not None]
        ate = sum(map(float, raw_ate))/len(raw_ate) if len(raw_ate) == len(rows) else None
        sim = pooled(rows, 'ate_sim3_game_units', 'valid_pose_count')
        se = pooled(rows, 'ate_se3_game_units', 'valid_pose_count')
        result = dict(sequence=seq, environment=first['environment'], calibration_branch=first['calibration_branch'],
                      model=model, offset=off, nominal_seconds=off/15, independent_segments=len(rows),
                      available_source_frames=nframes, valid_pose_count=count(rows, 'valid_pose_count'),
                      segment_export_completions=sum(r['export_completion'] == 'True' for r in rows),
                      keyframe_count=count(rows, 'keyframe_count'), missing_pose_count=count(rows, 'missing_pose_count'),
                      invalid_pose_count=count(rows, 'invalid_pose_count'), expected_pair_count=n, valid_pair_count=nvalid,
                      invalid_pair_count=n-nvalid, common_valid_pair_count=count(rows, 'common_valid_pair_count'),
                      coverage_ratio=nvalid/n if n else None, **scores,
                      sequence_mean_segment_sim3_ate_path_pct=ate, sequence_pooled_sim3_ate_game_units=sim,
                      sequence_pooled_se3_ate_game_units=se)
        old = existing[seq]
        prefix = 'slam_' if model == MODELS[0] else 'wild_'
        for a, b in (('translation_rpe_sim3_game_units', f'rpe_translation_sim3_{off}'),
                     ('rotation_rpe_deg', f'rpe_rotation_deg_{off}'),
                     ('sequence_mean_segment_sim3_ate_path_pct','sequence_mean_normalized_ate_pct'),
                     ('sequence_pooled_sim3_ate_game_units','sequence_pooled_sim3_ate_game_units'),
                     ('sequence_pooled_se3_ate_game_units','sequence_pooled_se3_ate_game_units')):
            x, y = result[a], val(old[prefix+b])
            require((x is None and y is None) or (x is not None and y is not None and np.isclose(x, y, atol=1e-7, rtol=1e-7)),
                    f'sequence metric reproduction mismatch {seq} {model} {off}: {a}')
            if x is not None:
                max_historical_gap = max(max_historical_gap, abs(x-y))
        results.append(result)
    return results, max_historical_gap


def env_groups(rows):
    for branch in (FIXED, VIRTUAL):
        for env in ('ALL', *ENVIRONMENTS):
            scope = [r for r in rows if r['calibration_branch'] == branch and (env == 'ALL' or r['environment'] == env)]
            if scope:
                yield branch, env, scope


def aggregate(seq):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    env_rows, paired = [], []
    for branch, env, rows in env_groups(seq):
        for off in OFFSETS:
            totals = {m: [r for r in rows if r['offset'] == off and r['model'] == m] for m in MODELS}
            for metric in METRICS:
                by_model = {}
                for m in MODELS:
                    group = totals[m]
                    eligible = [r for r in group if r[metric] is not None]
                    by_model[m] = {r['sequence']:r[metric] for r in eligible}
                    env_rows.append(dict(calibration_branch=branch, environment=env, model=m, offset=off,
                                         nominal_seconds=off/15, metric=metric, planned_sequences=len(group),
                                         eligible_sequences=len(eligible), valid_frames=count(group,'valid_pose_count'),
                                         valid_pair_count=count(group,'valid_pair_count'),
                                         invalid_pair_count=count(group,'invalid_pair_count'),
                                         common_valid_pair_count=count(group,'common_valid_pair_count'),
                                         pooled_rpe_pair_weighted=pooled(eligible,metric,'valid_pair_count'),
                                         **with_ci(list(by_model[m].values()), rng), stability=stability(len(eligible))))
                if metric == METRICS[2]:
                    # The locked unscaled translation mixes a model's native scale with game units.
                    continue
                keys = sorted(by_model[MODELS[0]].keys() & by_model[MODELS[1]].keys())
                a = np.asarray([by_model[MODELS[0]][s] for s in keys])
                b = np.asarray([by_model[MODELS[1]][s] for s in keys])
                d = b-a
                draws = rng.integers(0, len(keys), size=(BOOTSTRAP_DRAWS, len(keys))) if len(keys) > 1 else None
                n = len(keys)
                wwin, swin = int((d < -1e-10).sum()), int((d > 1e-10).sum())
                stats = with_ci(d, rng, draws)
                a_ci, b_ci = bootstrap_ci(a, draws), bootstrap_ci(b, draws)
                paired.append(dict(calibration_branch=branch, environment=env, offset=off, nominal_seconds=off/15,
                                   metric=metric, planned_sequences=len(totals[MODELS[0]]), paired_sequences=n,
                                   paired_sequence_ids=';'.join(keys), droid_slam_mean=float(a.mean()) if n else None,
                                   droid_w_mean=float(b.mean()) if n else None,
                                   droid_slam_ci95_low=a_ci[0], droid_slam_ci95_high=a_ci[1],
                                   droid_w_ci95_low=b_ci[0], droid_w_ci95_high=b_ci[1],
                                   mean_relative_gap_pct=100*float(d.mean())/float(a.mean()) if n and a.mean()>0 else None,
                                   **stats, droid_w_lower_error_sequences=wwin, droid_slam_lower_error_sequences=swin,
                                   ties=n-wwin-swin, bootstrap_seed=BOOTSTRAP_SEED,
                                   bootstrap_draws=BOOTSTRAP_DRAWS if draws is not None else 0, stability=stability(n)))
    return env_rows, paired


def summarize_compression(screen):
    result = []
    for branch, env, values in env_groups(screen):
        for offset in (*OFFSETS, 16, 52):
            for scope in ('all', 'excludes_val_007'):
                rows = [r for r in values if int(r['offset']) == offset and
                        (scope == 'all' or r['sequence'] != 'val_007')]
                if not rows:
                    continue
                any_cases = [r for r in rows if int(r['wild_specific_pairs']) > 0]
                sustained_cases = [r for r in rows if int(r['wild_specific_runs_ge5']) > 0]
                seq = sorted({r['sequence'] for r in sustained_cases})
                result.append(dict(calibration_branch=branch, environment=env, offset=offset,
                                   designated_RPE_offset=offset in OFFSETS, anchor_scope=scope,
                                   sequences=len({r['sequence'] for r in rows}), segments=len(rows),
                                   gt_screened_common_pairs=count(rows,'eligible_motion_pairs'),
                                   wild_step_less_than_half_gt=count(rows,'suppressed_wild_pairs'),
                                   slam_step_less_than_half_gt=count(rows,'suppressed_slam_pairs'),
                                   both_step_less_than_half_gt=count(rows,'both_suppressed_pairs'),
                                   wild_specific_pairs=count(rows,'wild_specific_pairs'),
                                   wild_specific_any_segments=len(any_cases),
                                   wild_specific_any_sequences=len({r['sequence'] for r in any_cases}),
                                   wild_specific_sustained_segments=len(sustained_cases),
                                   wild_specific_sustained_sequences=len(seq),
                                   wild_specific_sustained_sequence_ids=';'.join(seq)))
    return result


def cross_metric(seq):
    index = {(r['sequence'],r['model'],r['offset']):r for r in seq}
    result = []
    def winner(d):
        return 'DROID-W' if d < -1e-10 else 'DROID-SLAM' if d > 1e-10 else 'TIE'
    for x in [r for r in seq if r['model'] == MODELS[0]]:
        y = index[x['sequence'], MODELS[1], x['offset']]
        if (x[METRICS[0]] is None or y[METRICS[0]] is None or x[METRICS[1]] is None or y[METRICS[1]] is None
                or x['sequence_mean_segment_sim3_ate_path_pct'] is None or y['sequence_mean_segment_sim3_ate_path_pct'] is None):
            continue
        ga, gb = [r['sequence_mean_segment_sim3_ate_path_pct'] for r in (x,y)]
        ta,tb,ra,rb = x[METRICS[0]],y[METRICS[0]],x[METRICS[1]],y[METRICS[1]]
        result.append(dict(sequence=x['sequence'], environment=x['environment'], calibration_branch=x['calibration_branch'],
                           offset=x['offset'], droid_slam_sim3_ate_path_pct=ga, droid_w_sim3_ate_path_pct=gb,
                           droid_slam_translation_rpe=ta,droid_w_translation_rpe=tb,
                           droid_slam_rotation_rpe_deg=ra,droid_w_rotation_rpe_deg=rb,
                           ate_preferred_model=winner(gb-ga), translation_rpe_preferred_model=winner(tb-ta),
                           rotation_rpe_preferred_model=winner(rb-ra),
                           ate_translation_disagree=winner(gb-ga) != winner(tb-ta)))
    return result


def main():
    full = [r for r in read_csv(OUT/'R2_RPE_PER_SEGMENT.csv') if r['scope'] == 'full']
    require(len(full) == 92*4*2,'expected all formal R2 segment/model/offset combinations')
    require({r['calibration_branch'] for r in full} == {FIXED,VIRTUAL}, 'missing branch')
    seq, maxdrift = by_sequence(full)
    require(len(seq) == 47*4*2,'expected complete sequence table')
    grouped, bootstrap = aggregate(seq)
    cmp = summarize_compression(read_csv(OUT/'R2_LOCAL_TRANSLATION_COMPRESSION_SCREEN.csv'))
    agreement = cross_metric(seq)
    save_csv('R2_RPE_PER_SEQUENCE.csv',seq)
    save_csv('R2_RPE_ENVIRONMENT_SUMMARY.csv',grouped)
    save_csv('R2_SEQUENCE_BOOTSTRAP_COMPARISON.csv',bootstrap)
    save_csv('R2_COMPRESSION_BY_ENVIRONMENT.csv',cmp)
    save_csv('R2_ATE_RPE_AGREEMENT.csv',agreement)
    save_csv('R2_VAL007_RPE_BY_SCOPE.csv',[r for r in read_csv(OUT/'R2_RPE_PER_SEGMENT.csv') if r['sequence'] == 'val_007'])
    save_json('R2_STATISTICAL_CONTRACT.json', dict(
        sequence_count=47, segment_count=92, scope='full per segment, no cross-segment pose pairing',
        maximum_sequence_metric_drift_from_original=maxdrift, statistic='Arithmetic mean of sequence-level paired RMSE differences',
        sequence_rmse='sqrt(sum(per-segment RMSE^2 * eligible motion pairs) / sum(eligible motion pairs))',
        bootstrap_draws=BOOTSTRAP_DRAWS, bootstrap_seed=BOOTSTRAP_SEED, confidence_interval='percentile 95%, sequence resampled with replacement',
        model_ci='marginal per-model mean intervals; pair-comparison CI resamples matching sequences together',
        p90_p95='across sequence-level RMSEs; not a motion-pair distribution',
        std='sample standard deviation, ddof=1', n_lt_5='descriptive, unstable', n_eq_1='no CI',
        compression_screen=dict(relative_gt_step_floor='0.5× median nonzero GT displacement in the same segment and offset',
                                minimum_nonzero_gt_game_units=1e-6, wild_displacement_ratio_lt=.5,
                                slam_displacement_ratio_between=[.8,1.2], consecutive_start_ids_minimum=5,
                                exact_case_offsets=[16,52], interpretation='descriptive recurrence screen, overlapping starts not independent')))
    print(f'PASS sequence aggregation: {len(seq)} rows, {len(grouped)} environment metric rows, {len(bootstrap)} paired rows. '
          f'Max frozen sequence score delta={maxdrift:.3g}.')


if __name__ == '__main__':
    main()
