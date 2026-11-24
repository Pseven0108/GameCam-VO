"""Stream native observer JSONL into the six Task 003 evidence tables (CPU)."""
import argparse
from collections import Counter
from contextlib import ExitStack
import csv
import hashlib
import json
from pathlib import Path


SCHEMA = 'GAMECAM_TASK003_RUNTIME_OBSERVER_V1'
BASE = 'event type stage pid time_unix_ns trigger_rgb_id outer_iteration filler_batch ba_id capture_and_summary_ns copy_to_cpu_ns'
BA = {'ba_before', 'ba_after_native', 'ba_after_clamp'}
POSE = 'rows t0 t1 native_iterations_requested motion_only source_uba target_uba update_u metric_depth_configured metric_depth_branch_active gamma_depth edge_slots sample_edge_indices disparity geometry float32_floor_count'
TABLES = {
    'KEYFRAME_EVENT_LOG': 'outcome local_initialized before_count after_count score threshold forced native_decision_proxy pose_init row rows disparity predicted_depth native_mono_prior',
    'FRONTEND_LOCAL_BA_LOG': POSE,
    'FINAL_BA_ITERATION_LOG': POSE,
    'METRIC_DEPTH_SUMMARY': 'rgb_id gamma_depth metric_depth_configured metric_depth_branch_active metric_depth_positive_support prior_support predicted_depth native_mono_prior disparity positive_depth float32_floor_count',
    'UNCERTAINTY_SUMMARY': 'source_uba target_uba update_u affine_u gamma_data gamma_prior sample_grid_step uncertainty geometry',
    'FILLER_UPDATE_LOG': 'update_number native_iterations_requested motion_only source_uba target_uba update_u rows bracket_rows geometry anchor_rgb_ids',
}


def basename(table):
    return f'TASK003_{table}.csv'


def queues(event):
    name, stage = event['type'], event['stage']
    if name in {'keyframe_candidate_inserted', 'keyframe_decision', 'motion_filter_score', 'frontend_distance', 'tracking_start'}:
        yield 'KEYFRAME_EVENT_LOG'
    if name == 'keyframe_candidate_inserted' or name in BA:
        yield 'METRIC_DEPTH_SUMMARY'
    if name in {'ba_before', 'ba_after_native'}:
        yield 'UNCERTAINTY_SUMMARY'
    if stage.startswith('frontend_') and (name in BA or name == 'stage_boundary'):
        yield 'FRONTEND_LOCAL_BA_LOG'
    if stage.startswith('final_') and (name in BA or name == 'stage_boundary'):
        yield 'FINAL_BA_ITERATION_LOG'
    if name.startswith('filler_') or name == 'export_matrix' or (stage == 'filler_pose_only' and name in BA):
        yield 'FILLER_UPDATE_LOG'


def reject_nonfinite(token):
    raise ValueError(f'nonstandard JSON token {token}')


def check(line, seq, pid):
    if not line.endswith(b'\n'):
        raise ValueError('unterminated event')
    event = json.loads(line, parse_constant=reject_nonfinite)
    if (event['schema'] != SCHEMA or event['event'] != seq or type(event['pid']) is not int
            or (pid is not None and event['pid'] != pid)
            or not isinstance(event['type'], str) or not isinstance(event['stage'], str)):
        raise ValueError(f'mismatched schema, event order or tracking process at event {seq}')
    if seq == 1 and event['type'] != 'tracking_start':
        raise ValueError('missing tracking_start')
    rows = (event.get('rows') or []) + ([event['row']] if event.get('row') else [])
    for row in rows:
        if (not 1 <= row['rgb_id'] <= 487 or row['slot'] < 0 or len(row['w2c_xyzw']) != 7
                or row['pool'] not in {'KEYFRAME_CACHE', 'FILLER_TEMP'}):
            raise ValueError('invalid pose identity')
    if event['type'] == 'export_matrix' and (event['rgb_ids'] != list(range(1, 488)) or len(event['c2w']) != 487):
        raise ValueError('incorrect export frame identity or cardinality')
    return event


def convert(out, trace):
    counts, observed, native_returns = Counter(), Counter(), Counter()
    pid, error = None, None
    size = 0
    sha = hashlib.sha256()
    with ExitStack() as stack:
        writers = {}
        for name, columns in TABLES.items():
            handle = stack.enter_context((out/basename(name)).open('x', encoding='utf-8', newline=''))
            writers[name] = csv.DictWriter(handle, (BASE+' '+columns).split(), extrasaction='ignore')
            writers[name].writeheader()

        if trace is not None:
            file = stack.enter_context(trace.open('rb'))
            for seq, line in enumerate(file, 1):
                sha.update(line)
                try:
                    event = check(line, seq, pid)
                    name, stage = event['type'], event['stage']
                    if observed['observer_overhead'] or (observed['export_matrix'] and name != 'observer_overhead'):
                        raise ValueError('unexpected event after terminal export')
                    if name == 'observer_overhead' and not observed['export_matrix']:
                        raise ValueError('missing export before terminal overhead summary')
                except (ValueError, TypeError, KeyError) as exc:
                    error = f'Event {seq}: {exc}'
                    break
                size += len(line)
                pid = event['pid']
                observed[name] += 1
                if name == 'ba_after_native':
                    native_returns[stage] += 1
                fields = {k: (json.dumps(v, separators=(',', ':'), allow_nan=False)
                              if isinstance(v, (list, dict)) else v)
                          for k,v in event.items() if k != 'c2w'}
                if event.get('row'):
                    fields['rgb_id'] = event['row']['rgb_id']
                for table in queues(event):
                    writers[table].writerow(fields)
                    counts[table] += 1
            for remaining in file:
                sha.update(remaining)

    status = ('UNVERIFIED_RUN_NOT_STARTED' if trace is None else
              'TRACE_HAS_TERMINAL_EXPORT' if not error and observed['observer_overhead'] else 'PARTIAL_TRACE')
    receipt = dict(status=status, runtime_process_exit_code=None, trace=str(trace) if trace is not None else None,
                   trace_sha256=sha.hexdigest() if trace is not None else None, observed_pid=pid,
                   validated_prefix_bytes=size, trace_error=error, events_by_type=dict(observed),
                   native_ba_calls_returned=dict(native_returns),
                   rows_by_file={basename(name): counts[name] for name in TABLES})
    with (out/'TASK003_TRACE_PROCESSING.json').open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--events', type=Path)
    mode.add_argument('--not-started', action='store_true')
    args = parser.parse_args()
    if args.events is not None and not args.events.is_file():
        parser.error('--events must be an existing trace')
    if any((args.out/name).exists() for name in [*(basename(t) for t in TABLES), 'TASK003_TRACE_PROCESSING.json']):
        parser.error('refusing to overwrite an earlier conversion')
    args.out.mkdir(parents=True, exist_ok=True)
    report = convert(args.out, args.events)
    print(json.dumps(report, indent=2))
    raise SystemExit(2 if report['trace_error'] else 0)
