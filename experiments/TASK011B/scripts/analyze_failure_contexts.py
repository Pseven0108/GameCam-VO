"""Describe actual initialization/controlled-BA exposure without changing scores.

All planned outcomes remain in the denominator. A failure before the first
controlled joint Local BA cannot measure an intervention that never executed.
This script never launches a model, changes a window or imputes an accuracy.
"""
import csv,json
from common import TASK,csvwrite,dump


def main():
    if not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():
        raise RuntimeError('Final failure context requires the completed batch')
    with (TASK/'evaluation/VIPER_TRAJECTORY_METRICS.csv').open(encoding='utf-8-sig',newline='') as f:
        metrics=list(csv.DictReader(f))
    if len(metrics)!=140:raise RuntimeError('Preserve all140 planned outcomes')
    rows=[]
    for metric in metrics:
        root=TASK/'gpu_results/raw'/('window_'+metric['window']+'_'+metric['arm'])/'result'
        failure=json.loads((root/'ALGORITHM_FAILURE.json').read_text()) if (root/'ALGORITHM_FAILURE.json').exists() else {}
        exception=json.loads((root/'CHILD_EXCEPTION.json').read_text()) if (root/'CHILD_EXCEPTION.json').exists() else {}
        complete=json.loads((root/'TRACKING_CHILD_COMPLETE.json').read_text()) if (root/'TRACKING_CHILD_COMPLETE.json').exists() else {}
        calls=[json.loads(line) for line in (root/'native_ba_calls.jsonl').read_text().splitlines()] if (root/'native_ba_calls.jsonl').exists() else []
        controlled=sum(bool(call['intervention']) for call in calls)
        if metric['success']=='True' and failure:raise RuntimeError('Conflicting completed/failure receipts')
        rows.append(dict(window=metric['window'],sequence=metric['sequence'],environment=metric['environment'],
            arm=metric['arm'],status=metric['status'],complete_64_frame_trajectory=metric['success']=='True',
            failure_status=failure.get('status'),accepted_keyframes_at_exit=failure.get('keyframes',complete.get('keyframes')),
            logged_native_BA_calls=len(calls),logged_controlled_BA_calls=controlled,
            failure_before_any_controlled_BA=bool(failure) and controlled==0,
            exception_type=exception.get('type'),exception_message=exception.get('error'),
            accuracy_missing_not_imputed=metric['success']!='True'))
    groups=[]
    for window in sorted({row['window'] for row in rows}):
        own=[row for row in rows if row['window']==window]
        if len(own)!=7:raise RuntimeError('Incomplete window arm set')
        refs=[row for row in own if row['arm'] in ('A0','A1')]
        groups.append(dict(window=window,environment=own[0]['environment'],planned_arms=7,
            completed_arms=sum(row['complete_64_frame_trajectory'] for row in own),
            failures_before_any_controlled_BA=sum(row['failure_before_any_controlled_BA'] for row in own),
            original_endpoint_controls_both_complete=all(row['complete_64_frame_trajectory'] for row in refs),
            all_seven_failed_initialization=all(row['failure_status']=='TRACKING_INITIALIZATION_FAILED' for row in own),
            min_accepted_keyframes=min((row['accepted_keyframes_at_exit'] for row in own if row['accepted_keyframes_at_exit'] is not None),default=None),
            max_accepted_keyframes=max((row['accepted_keyframes_at_exit'] for row in own if row['accepted_keyframes_at_exit'] is not None),default=None)))
    csvwrite(TASK/'evaluation/VIPER_FAILURE_CONTEXT_ALL_140.csv',rows)
    csvwrite(TASK/'evaluation/VIPER_FAILURE_CONTEXT_BY_WINDOW.csv',groups)
    before=sum(row['failure_before_any_controlled_BA'] for row in rows)
    failed=sum(not row['complete_64_frame_trajectory'] for row in rows)
    dump(TASK/'evaluation/FAILURE_CONTEXT_STATUS.json',dict(
        status='ACTUAL_FAILURE_STAGE_AND_INTERVENTION_EXPOSURE',formal_outcomes=140,
        failures=failed,failures_before_any_controlled_BA=before,
        all_seven_initialization_failure_windows=sum(row['all_seven_failed_initialization'] for row in groups),
        original_accuracy_and_completion_tables_unchanged=True,
        no_failure_imputation=True,no_new_GPU_runs=True,
        interpretation='A pre-control initialization failure does not identify a reliability intervention effect. A0 has no intervention by design; compare the full window arm set and the recorded failure stage.'))
    lines=['# Actual failure context and intervention exposure','',
        f'All140 planned outcomes are retained. {failed} lack a complete64-frame trajectory; {before} failed before any controlled BA was logged. No accuracy is imputed.', '',
        'Frozen native warmup is12 accepted keyframes. The original observer guard preserves a partial uninitialized state instead of fabricating a full trajectory. No warmup, frame count, selection or algorithm parameter was adjusted after observing failures.', '',
        '| Window | Environment | Complete /7 | Pre-control failures | All7 init failures | Accepted KF range |',
        '|---|---|---:|---:|---|---|']
    for row in groups:
        lines.append(f"| {row['window']} | {row['environment']} | {row['completed_arms']} | {row['failures_before_any_controlled_BA']} | {row['all_seven_failed_initialization']} | {row['min_accepted_keyframes']}–{row['max_accepted_keyframes']} |")
    lines.extend(['','An entire seven-arm set failing before controlled Local BA cannot support a claim that CADP-DR improved or damaged tracking. Such cases still count against the planned-window completion rate. Their image files need not be duplicates, and insufficient accepted motion is not proof of frozen RGB.', '',
        'The accepted-keyframe count at exit and actual logged BA exposure are observations. They do not establish the physical cause of initialization failure or predict whether a longer sequence would succeed. No replacement or longer-window experiment was run.'])
    (TASK/'evaluation/VIPER_FAILURE_STAGE_ANALYSIS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('ACTUAL_FAILURE_CONTEXT',len(rows),failed,before,flush=True)


if __name__=='__main__':main()
