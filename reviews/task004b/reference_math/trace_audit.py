"""Pair native BA records without interleaving different processes or calls."""
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from contracts import BITS, IDS, LOCAL_STAGES, TARGET, need, strict_json


HIST = 'GAMECAM_TASK003_RUNTIME_OBSERVER_V1'
CANDIDATE = 'GAMECAM_TASK004_RUNTIME_OBSERVER_CANDIDATE_V1'
BEFORE, NATIVE, CLAMP = 'ba_before', 'ba_after_native', 'ba_after_clamp'
CONTEXT = ('stage', 'trigger_rgb_id', 'outer_iteration', 'filler_batch')
BASELINE_FLAGS = {
    'frontend_init_neighborhood': (True, False, True, False),
    'frontend_init_proximity': (True, True, True, False),
    'frontend_init_second': (True, True, True, False),
    'final_ba_phase_1': (False, True, False, False),
    'final_ba_phase_2': (False, True, False, False),
    'filler_pose_only': (False, True, False, True),
}
DECISION = {'LOCAL_BA_REJECTED', 'MOTION_FILTER_REJECTED', 'RETAINED', 'RETAINED_WARMUP_PENDING'}
MAX_LINE = 8 * 1024**2
MAX_TRACE = 384 * 1024**2


def same_context(a, b):
    return all(a[k] == b[k] for k in CONTEXT)


def pose_index(event, pool):
    rows = event['rows']
    ids = [r['rgb_id'] for r in rows]
    slots = [r['slot'] for r in rows]
    need(all(type(i) is int for i in slots + ids) and slots == sorted(set(slots))
         and len(ids) == len(set(ids)) and all(i in IDS for i in ids)
         and all(r['pool'] == pool for r in rows), f'invalid {pool} snapshot at event {event["event"]}')
    return {r['rgb_id']: r for r in rows}


def check_flags(row, arm):
    phase = row['stage']
    if phase in LOCAL_STAGES:
        expected = tuple(bool(x) for x in (BITS[arm] if arm else (1, 1, 1))) + (False,)
    else:
        need(phase in BASELINE_FLAGS, f'unrecognized BA stage: {phase}')
        expected = BASELINE_FLAGS[phase]
    observed = tuple(row[k] for k in ('metric_depth_branch_active', 'source_uba', 'update_u', 'motion_only'))
    need(all(type(x) is bool for x in observed) and observed == expected
         and row['target_uba'] is False and row['gamma_depth'] == 0.01, f'{phase} native flag receipt mismatch')
    if arm:
        need(row['task004_local_phase'] == (phase if phase in LOCAL_STAGES else None), 'wrong intervention scope')
        if phase in LOCAL_STAGES:
            need(row['metric_depth_configured'] is True and row['metric_depth_prior_selected'] is expected[0],
                 'local prior branch receipt mismatch')
            need(type(row['cached_prior_positive_support']) is int and row['cached_prior_positive_support'] >= 0,
                 'missing retained prior-cache observation')
            need(type(row['metric_depth_positive_support']) is int
                 and row['metric_depth_positive_support'] == (row['cached_prior_positive_support'] if expected[0] else 0),
                 'wrong effective prior support')


def clamp_counts(event, expected_slots):
    if event['schema'] == HIST:
        return None  # Task003 saved sampled disparity statistics, not Task004's full counters.
    g = event['full_disparity_grid']
    counts = [g[k] for k in ('total', 'negative', 'nonfinite', 'float32_floor_count')]
    need(g['scope'] == 'ALL_PIXELS_ACTIVE_SLOT_PREFIX' and g['active_slots'] == expected_slots
         and all(type(x) is int and x >= 0 for x in counts) and counts[0] == expected_slots * 80 * 45
         and sum(counts[1:]) <= counts[0], 'invalid full disparity counters')
    return g


def track_snapshot(row):
    return {i: (p['slot'], p['pool']) for i, p in pose_index(row, 'KEYFRAME_CACHE').items()}


def paired(before, native, clamp):
    key = track_snapshot(before) if before['stage'] != 'filler_pose_only' else None
    if key is None:  # A Filler BA includes native anchors and temporary slots in the same active prefix.
        signature = lambda a: [(p['slot'], p['rgb_id'], p['pool']) for p in a['rows']]
        need(signature(before) == signature(native), 'filler slot identity changed during a native call')
    else:
        need(key == track_snapshot(native), 'keyframe slot identity changed during native BA')
    n = len(before['rows'])
    t0, t1 = before['t0'], before['t1']
    need(type(t0) is int and type(t1) is int and 0 <= t0 <= t1 <= n, 'invalid BA slot window')
    edges = before['edge_slots']
    need(all(len(e) == 2 and all(type(i) is int and 0 <= i < n for i in e) for e in edges), 'invalid BA edges')
    gn, gc = (clamp_counts(event, n) for event in (native, clamp))
    report = dict(pid=before['pid'], ba_id=before['ba_id'], stage=before['stage'], trigger_rgb_id=before['trigger_rgb_id'],
                  outer_iteration=before['outer_iteration'], filler_batch=before['filler_batch'],
                  before_event=before['event'], native_event=native['event'], clamp_event=clamp['event'],
                  native_negative=None if gn is None else gn['negative'],
                  clamp_negative=None if gc is None else gc['negative'],
                  native_grid=gn, clamp_grid=gc)
    if gc is not None:
        need(gn['total'] == gc['total'] and gc['negative'] == 0,
             'Python clamp receipt inconsistent with native grid')
    poses = None
    if key is not None and set(TARGET) <= key.keys() and before['stage'] in LOCAL_STAGES:
        a, b = (key[i][0] for i in TARGET)
        touched = {slot for edge in edges for slot in edge}
        report.update(endpoint_slots=[a, b], both_in_pose_window=t0 <= a < t1 and t0 <= b < t1,
                      both_observed_in_edges={a, b} <= touched, direct_edge=any(set(e) == {a, b} for e in edges))
        poses = {tag: {p['rgb_id']: p for p in e['rows'] if p['rgb_id'] in TARGET}
                 for tag, e in (('before', before), ('native', native))}
    return report, poses


@dataclass
class Trace:
    sha256: str = ''
    bytes: int = 0
    pids: dict = field(default_factory=dict)
    events: Counter = field(default_factory=Counter)
    decisions: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)
    unfinished: list = field(default_factory=list)
    common: list = field(default_factory=list)
    boundaries: dict = field(default_factory=dict)
    filler: dict = field(default_factory=dict)
    filler_interpolated: dict = field(default_factory=dict)
    export: dict | None = None
    overhead_count: int = 0

    def summary(self):
        returned = [x for x in self.calls if x['stage'] in LOCAL_STAGES]
        return dict(sha256=self.sha256, bytes=self.bytes, pid_event_counts=self.pids,
                    events=dict(self.events), calls=len(self.calls), calls_by_stage=dict(Counter(x['stage'] for x in self.calls)),
                    local_returned=len(returned), local_returned_rejected=sum(x['candidate_decision'] == 'LOCAL_BA_REJECTED' for x in returned),
                    local_joint_snapshot_calls=len(self.common),
                    local_both_in_pose_window=sum(r['both_in_pose_window'] for r, _ in self.common),
                    local_both_in_pose_window_and_observed=sum(r['both_in_pose_window'] and r['both_observed_in_edges'] for r, _ in self.common),
                    unfinished=self.unfinished, keyframe_decisions=len(self.decisions),
                    filler_batch_output_frames=len(self.filler), export_event=self.export and self.export['event'])


def parse(path, *, arm=None, complete=False, expected_pid=None):
    """Historical schema only when arm is None; never validate old evidence as an arm."""
    schema = HIST if arm is None else CANDIDATE
    report, sha = Trace(), hashlib.sha256()
    pending, last_ba = {}, defaultdict(int)
    filler_batches, finished_batches, filler_steps = {}, {}, defaultdict(list)
    with Path(path).open('rb') as stream:
        while line := stream.readline(MAX_LINE + 1):
            need(len(line) <= MAX_LINE and line.endswith(b'\n') and report.bytes + len(line) <= MAX_TRACE,
                 'partial JSONL line or observer budget exceeded')
            row = strict_json(line)
            sha.update(line)
            pid, num, kind = (row[k] for k in ('pid', 'event', 'type'))
            need(row['schema'] == schema and type(pid) is int and pid > 0
                 and type(num) is int and (expected_pid is None or pid == expected_pid), 'trace schema or PID mismatch')
            need(num == report.pids.get(pid, 0) + 1, 'per-process trace index discontinuity')
            report.pids[pid] = num
            report.events[kind] += 1
            if pid in pending:
                need(kind in (NATIVE, CLAMP), 'missing BA return/clamp within tracking process')
            if kind == 'tracking_start':
                need(num == 1 and row['stage'] == 'startup'
                     and all(row[k] is False for k in ('enable_online_ba', 'enable_loop', 'mapping_enabled'))
                     and row['droidvis'] is True and row['backend_stride'] == 8, 'wrong tracking startup envelope')
            elif kind == BEFORE:
                ba_id = row['ba_id']
                need(type(ba_id) is int and ba_id == last_ba[pid] + 1, 'BA call index discontinuity')
                last_ba[pid] = ba_id
                check_flags(row, arm)
                pending[pid] = [row]
            elif kind in (NATIVE, CLAMP):
                p = pending.get(pid, ())
                need(len(p) == (1 if kind == NATIVE else 2) and type(row['ba_id']) is int
                     and row['ba_id'] == p[0]['ba_id'] and same_context(row, p[0]), 'orphan or mismatched BA return/clamp')
                p.append(row)
                if kind == CLAMP:
                    record, poses = paired(*p)
                    report.calls.append(record)
                    if poses is not None:
                        report.common.append((record, poses))
                    del pending[pid]
            elif kind == 'keyframe_decision':
                i = row['trigger_rgb_id']
                decision = row['outcome']
                need(type(i) is int and i in IDS and (pid, i) not in report.decisions and decision in DECISION,
                     'invalid or duplicate keyframe decision')
                report.decisions[pid, i] = decision
            elif kind == 'stage_boundary':
                stage = row['stage']
                need(stage not in report.boundaries, f'duplicate boundary: {stage}')
                report.boundaries[stage] = row
            elif kind in ('filler_interpolated', 'filler_batch_result'):
                batch = (pid, row['filler_batch'])
                rows = pose_index(row, 'FILLER_TEMP')
                need(type(batch[1]) is int and batch[1] > 0 and bool(rows), 'invalid filler batch')
                if kind == 'filler_interpolated':
                    need(batch not in filler_batches and not set(rows) & report.filler_interpolated.keys(), 'duplicate filler start')
                    report.filler_interpolated.update(rows)
                    filler_batches[batch] = (num, tuple(rows))
                else:
                    need(batch in filler_batches and filler_batches[batch][1] == tuple(rows) and batch not in finished_batches
                         and not set(rows) & report.filler.keys(), 'filler result without an identical frame list')
                    report.filler.update({i: dict(p, audit_batch=batch[1]) for i, p in rows.items()})
                    finished_batches[batch] = num
            elif kind == 'filler_pose_update':
                batch = (pid, row['filler_batch'])
                rows = pose_index(row, 'FILLER_TEMP')
                need(batch in filler_batches and batch not in finished_batches
                     and tuple(rows) == filler_batches[batch][1], 'filler update frame list mismatch')
                filler_steps[batch].append((num, row['ba_id'], row['update_number'], row['outer_iteration']))
            elif kind == 'export_matrix':
                need(report.export is None and row['stage'] == 'export_matrix_after_anchor_reinsertion', 'unexpected export receipt')
                report.export = row
            elif kind == 'observer_overhead':
                need(report.export is not None and report.export['event'] + 1 == num and report.overhead_count == 0
                     and row['events_before_summary'] == num - 1 and row['bytes_before_summary'] == report.bytes,
                     'trace completion receipt mismatch')
                report.overhead_count += 1
            if report.overhead_count:
                need(kind == 'observer_overhead', 'event written after terminal observer receipt')
            report.bytes += len(line)

    report.sha256 = sha.hexdigest()
    for call in report.calls:
        decision = report.decisions.get((call['pid'], call['trigger_rgb_id'])) if call['stage'] in LOCAL_STAGES else None
        call['candidate_decision'] = decision
        if complete and call['stage'] in LOCAL_STAGES:
            need(decision is not None and decision != 'MOTION_FILTER_REJECTED', 'local-BA call cannot be attached to a keyframe candidate decision')
    for pid, p in pending.items():
        report.unfinished.append(dict(pid=pid, ba_id=p[0]['ba_id'], before_event=p[0]['event'],
                                      status='NATIVE_RETURN_NOT_OBSERVED' if len(p) == 1 else 'CLAMP_NOT_OBSERVED'))
    if complete:
        need(len(report.pids) == 1 and not report.unfinished and report.events['tracking_start'] == 1
             and report.overhead_count == 1, 'partial or ambiguous tracking trace')
        need(tuple(i for _, i in report.decisions) == IDS, 'missing or misordered keyframe decisions')
        final = ('final_pre', 'final_ba_phase_1', 'final_phase_1_done', 'final_ba_phase_2', 'final_phase_2_done')
        need(all(k in report.boundaries for k in final), 'missing Final BA phase boundary')
        enclosing = [report.boundaries[k]['event'] for k in final] + [report.export['event']]
        need(enclosing == sorted(set(enclosing)) and all(t[0]['native_event'] < enclosing[0] for t in report.common),
             'misordered Final BA/export')
        by_stage = Counter(r['stage'] for r in report.calls)
        for stage, count, left, right in (('final_ba_phase_1', 7, 1, 2), ('final_ba_phase_2', 12, 3, 4)):
            selected = [r for r in report.calls if r['stage'] == stage]
            need(len(selected) == count and all(enclosing[left] < r['before_event'] < r['clamp_event'] < enclosing[right]
                                               for r in selected), 'Final BA call envelope mismatch')
        need(tuple(report.filler) == IDS and finished_batches.keys() == filler_batches.keys()
             and by_stage['filler_pose_only'] == 12 * len(finished_batches) and by_stage['filler_pose_only'] > 0,
             'incomplete or misordered Filler evidence')
        by_batch = defaultdict(list)
        for call in report.calls:
            if call['stage'] == 'filler_pose_only':
                by_batch[call['pid'], call['filler_batch']].append(call)
        need(by_batch.keys() == finished_batches.keys() == filler_steps.keys(), 'unpaired Filler batch')
        prior_end = enclosing[-2]
        for index, (batch, (start, ids)) in enumerate(filler_batches.items(), 1):
            steps, end, calls = filler_steps[batch], finished_batches[batch], by_batch[batch]
            need(batch[1] == index and ids == IDS[(index-1)*16:index*16]
                 and prior_end < start < end < enclosing[-1] and len(calls) == len(steps) == 12,
                 'Filler batch identity, coverage or phase mismatch')
            for i, (call, (ev, ba, step, outer)) in enumerate(zip(calls, steps), 1):
                need(start < call['before_event'] < call['clamp_event'] < ev < end
                     and ba == call['ba_id'] and step == outer == i == call['outer_iteration'],
                     'Filler update paired to wrong native call')
                start = ev
            prior_end = end
        need(any(by_stage[s] for s in LOCAL_STAGES), 'no observable main-loop local-BA intervention')
        need(all(not (r['stage'] in LOCAL_STAGES and r['clamp_event'] >= enclosing[0]) for r in report.calls),
             'local intervention recorded outside frontend')
    return report
