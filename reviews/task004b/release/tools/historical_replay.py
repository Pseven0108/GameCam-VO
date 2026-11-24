"""Verify local sealed identities and replay the Task003 trace without running a model."""
import argparse
import csv
from collections import Counter
import hashlib
from pathlib import Path

from contracts import (COMMIT, CONFIG_SHA, INPUT_SHA, IDS, GT_SHA, ROOT, TARGET, TENSOR_SHA,
                       history_inputs, need, new_json, read_json, stat_sha, utc, verify_matrix)
from endpoints import evaluate, read_export, read_gt
from trace_audit import parse


def source_identity():
    audit = ROOT.parent/'DROID_SLAM_DROID_W_TASK001_STATIC_AUDIT/evidence'
    source = read_json(audit/'SOURCE_IDENTITY_VERIFICATION.json')['repositories']['DROID-W']
    ledger_path = audit/'SOURCE_ENTRY_VERIFICATION.csv'
    with ledger_path.open(encoding='utf-8-sig', newline='') as f:
        ledger = {r['path']:r for r in csv.DictReader(f) if r['repository'] == 'DROID-W'}
    tree_path = Path(source['archive']).with_name('DROID-W-c3414af6047d-tree.json')
    tree = read_json(tree_path)
    entries = {r['path']:r for r in tree['tree'] if r['type'] != 'tree'}
    need(tree['sha'] == source['commit'] == COMMIT and not tree.get('truncated') and set(entries) == set(ledger),
         'frozen tree identities disagree')
    base = Path(source['snapshot'])
    details = {}
    for name, row in ledger.items():
        item = entries[name]
        need(row['git_mode'] == item['mode'] and row['git_sha1'] == item['sha'], f'{name}: tree/ledger mismatch')
        if row['git_mode'] == '160000':
            details[name] = dict(gitlink=item['sha'], scope='POINTER_ONLY')
            continue
        raw = (base/name).read_bytes()
        git = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        need(item['type'] == 'blob' and int(row['bytes']) == item['size'] == len(raw)
             and git == row['git_sha1'], f'{name}: snapshot blob mismatch')
        details[name] = dict(bytes=len(raw), git_blob_sha1=git, sha256=hashlib.sha256(raw).hexdigest())
    sizes = Counter('blob' if 'bytes' in r else 'gitlink' for r in details.values())
    need(sizes == {'blob':208, 'gitlink':3}, 'unexpected frozen source inventory')
    return dict(commit=COMMIT, snapshot=str(base), evidence_tree_sha256=stat_sha(tree_path),
                ledger_sha256=stat_sha(ledger_path), checked=dict(sizes), entries=details)


def run(out):
    archive_assets, archive = history_inputs(ROOT.parent/'DROID_W_TASK004_CAUSAL_ABLATION')
    need(all((ROOT/'assets'/name).read_bytes() == raw for name,raw in archive_assets.items()), 'staged review content differs')
    verify_matrix(ROOT/'assets')
    snapshot = source_identity()
    task = ROOT.parent/'DROID_W_TASK003_VAL007_OBSERVATION_R1'
    campaign = ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
    ledger = read_json(task/'FILE_SHA256_MANIFEST.json')['files']
    reused = ('remote/incoming/native_config.yaml', 'remote/incoming/INPUT.json', 'remote/capture/observer.jsonl',
              'remote/capture/keyframes.json', 'remote/capture/trajectory.npz', 'remote/capture/est_poses_full.txt',
              'remote/capture/model_input.json', 'remote/capture/model_result.json',
              'TASK003_VAL007_INTERVAL_ANALYSIS.csv', 'TASK003_312_328_LOCAL_BA_TIMELINE.csv')
    before = {n:stat_sha(task/n) for n in reused}
    need(all(before[n] == ledger[n]['sha256'] and (task/n).stat().st_size == ledger[n]['bytes'] for n in reused),
         'Task003 review input identities disagree')
    conf, rgb, gt_path = (task/reused[0], task/reused[1], campaign/'offline_gt/val_007.npz')
    need(stat_sha(conf) == CONFIG_SHA and stat_sha(rgb) == INPUT_SHA
         and [f['rgb_id'] for f in read_json(rgb)['frames']] == list(IDS), 'sealed R2 input mismatch')
    cap = task/'remote/capture'
    receipt = read_json(cap/'model_result.json')
    need(receipt['scaled_rgb_tensor_sha256'] == TENSOR_SHA and receipt['native_camera_messages'] > 0, 'historical receipt mismatch')
    trace = parse(cap/'observer.jsonl', complete=True, expected_pid=receipt['pid'])
    poses, keys = read_export(cap/'trajectory.npz', cap/'est_poses_full.txt', cap/'keyframes.json')
    need(len(poses) == receipt['poses_exported'] == len(IDS) and len(keys) == receipt['keyframes'], 'historical export coverage')
    retained, metrics, filler, local = evaluate('HISTORICAL_TASK003', 'TASK003_EXISTING', trace, poses, keys, read_gt(gt_path))
    with (task/'TASK003_VAL007_INTERVAL_ANALYSIS.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    prior = next(r for r in rows if r['stage'] == 'final_phase_2_done'
                 and (int(r['first_rgb']), int(r['last_rgb'])) == TARGET)
    need(abs(float(prior['length_est_native_units']) - metrics[1]['estimate_raw_length']) < 1e-8,
         'independent historical result comparison disagrees')
    need(len(trace.calls) == 1172 and trace.common[0][0]['ba_id'] == 552
         and trace.common[0][0]['before_event'] == 2600 and trace.common[0][0]['native_event'] == 2601
         and trace.common[0][0]['clamp_event'] == 2602, 'historical target-event crosscheck disagreement')
    need({n:stat_sha(task/n) for n in reused} == before and stat_sha(gt_path) == GT_SHA
         and source_identity() == snapshot, 'historical on-disk evidence changed during replay')
    new_json(out/'FROZEN_SOURCE_AND_HISTORY_RECHECK.json', dict(status='VERIFIED_READ_ONLY', checked_utc=utc(),
             task004_archive=archive, source=snapshot, task003=dict(root=str(task), files_sha256=before),
             offline_gt=dict(path=str(gt_path), sha256=GT_SHA, inference_inputs=0),
             note='Gitlink pointer identity only; current remote deployment and historical weights not reopened.'))
    observations = trace.summary()
    print(f"{sum(observations['events'].values())} historical events, {len(trace.calls)} complete BA calls, "
          f"{len(keys)} retained keyframes, {len(poses)} full export poses. First common BA: 552.")
    new_json(out/'TASK003_HISTORICAL_REPLAY.json', dict(status='HISTORICAL_ONLY_NOT_E0', evaluated_utc=utc(),
             trace=observations, retention=retained, endpoint_metrics=metrics, filler=filler, local_first_last=local,
             precision_note='Historical trace used sampled disparity only; no full-grid counts inferred.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    run(parser.parse_args().out)
