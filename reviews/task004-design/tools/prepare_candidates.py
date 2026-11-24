"""Build isolated Task 004 candidates from hash-verified local evidence. Never import SLAM."""

import ast
import csv
import difflib
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT.parent
SOURCE = EXP / 'DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources/DROID-W'
TASK001 = EXP / 'DROID_SLAM_DROID_W_TASK001_STATIC_AUDIT'
TASK002 = EXP / 'DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT'
TASK003 = EXP / 'DROID_W_TASK003_VAL007_OBSERVATION_R1'
INCOMING = TASK003 / 'remote/incoming'
CAPTURE = TASK003 / 'remote/capture'
SOURCE_TREE = SOURCE.parent.parent / 'inputs/DROID-W-c3414af6047d-tree.json'
COMMIT = 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'
RERUN = TASK003 / 'evidence/TASK003_FINAL_PREFLIGHT.json'
sys.path.insert(0, str(ROOT / 'candidates'))
import task004_controls as control


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = data.encode('utf-8') if isinstance(data, str) else data
    if path.is_file():
        check(path.read_bytes() == data, f'Existing output differs: {path}')
        return
    with path.open('xb') as handle:
        handle.write(data)


def write_json(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def replace(text, old, new):
    check(text.count(old) == 1, f'candidate edit preimage is not unique: {old[:100]!r}')
    return text.replace(old, new, 1)


def diff(old, new, path):
    return ''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        'a/' + path, 'b/' + path))


def git_apply(work, patch):
    git = shutil.which('git')
    check(git and work.parent.is_relative_to(ROOT), 'git or isolated sandbox unavailable')
    env = {k: v for k, v in os.environ.items() if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE')}
    env['GIT_CEILING_DIRECTORIES'] = str(work.parent)
    for mode in (['--check'], []):
        subprocess.run([git, '-c', 'core.autocrlf=false', 'apply', '--whitespace=nowarn', *mode, str(patch)],
                       cwd=work, env=env, check=True)


def patched_sources(base):
    out = dict(base)
    phase_call = r'(task003\(\)\.context\("(frontend_local_predecision|frontend_local_retained)", itr\+1\)\n\s*self\.graph\.update\([^)]*)\)'
    p = 'src/frontend.py'
    out[p], n = re.subn(phase_call, lambda m: m[1] + f', task004_phase="{m[2]}")', base[p])
    check(n == 2, f'Expected 2 local call sites with loop disabled, got {n}')

    p = 'src/factor_graph.py'
    out[p] = replace(base[p], 'enable_udba=True, visualization_stage=False):\n        """ run update operator on factor graph """',
                     'enable_udba=True, visualization_stage=False, *, task004_phase=None):\n        """ run update operator on factor graph """')
    out[p] = replace(out[p], 'visualization_stage=visualization_stage)\n        \n            self.video.upsample',
                     'visualization_stage=visualization_stage, task004_phase=task004_phase)\n        \n            self.video.upsample')

    p = 'src/depth_video.py'
    out[p] = 'from task004_controls import local_flags as task004_local_flags\n' + base[p]
    out[p] = replace(out[p], 'enable_udba=False, visualization_stage=False):      # ii, jj represent',
                     'enable_udba=False, visualization_stage=False, *, task004_phase=None):      # ii, jj represent')
    a = out[p].index('            task003().ba_before(')
    b = out[p].index('                droid_backends.ba(', a)
    out[p] = out[p][:a] + '''            observe = task003()
            use_depth, enable_udba, enable_update_uncer = task004_local_flags(
                task004_phase, observe.stage, self, motion_only, enable_update_uncer, enable_udba)
            observe.ba_before(self, target, weight, eta, ii, jj, t0, t1, iters, lm, ep, lr, weight_decay,
                              motion_only, enable_update_uncer, enable_udba, metric_selected=use_depth,
                              local_phase=task004_phase)
            if not use_depth:
''' + out[p][b:]

    p = 'task003_observer.py'
    out[p] = replace(base[p], "SCHEMA = 'GAMECAM_TASK003_RUNTIME_OBSERVER_V1'",
                     "SCHEMA = 'GAMECAM_TASK004_RUNTIME_OBSERVER_CANDIDATE_V1'")
    out[p] = replace(out[p], 'def ba_before(self,video,target,weight,eta,ii,jj,t0,t1,iters,lm,ep,lr,weight_decay,motion_only,update_u,use_u):',
                     '''def ba_before(self,video,target,weight,eta,ii,jj,t0,t1,iters,lm,ep,lr,weight_decay,motion_only,update_u,use_u,*,metric_selected,local_phase):''')
    out[p] = replace(out[p], 'used = bool(video.metric_depth_reg and not motion_only and h[\'gamma_depth\']!=0)',
                     "used = bool(metric_selected and not motion_only and h['gamma_depth']!=0)")
    out[p] = replace(out[p], "        prior_all = self.array(video.mono_disps[:n]) if used else None\n",
                     "        prior_all = self.array(video.mono_disps[:n]) if not motion_only else None\n")
    out[p] = replace(out[p], 'for i in kx] if used else []', 'for i in kx] if not motion_only else []')
    out[p] = replace(out[p], 'metric_depth_positive_support=sum(row[\'positive_mask_count\'] for row in counts),prior_support=counts,',
                     '''metric_depth_positive_support=sum(row['positive_mask_count'] for row in counts) if used else 0,
                  prior_support=counts if used else [],cached_prior_support=counts,
                  cached_prior_positive_support=sum(row['positive_mask_count'] for row in counts),
                  cached_prior_total=sum(row['total'] for row in counts),''')
    out[p] = replace(out[p], 'metric_depth_configured=bool(video.metric_depth_reg),metric_depth_branch_active=used,',
                     '''metric_depth_configured=bool(video.metric_depth_reg),metric_depth_branch_active=used,
                  metric_depth_prior_selected=bool(metric_selected),task004_local_phase=local_phase,
                  metric_depth_window_samples=int(len(kx)*video.mono_disps.shape[-2]*video.mono_disps.shape[-1]),''')
    out[p] = replace(out[p], '    live = valid & np.isfinite(effective).all(-1) & (effective>0).any(-1)',
                     '''    usable_weight = np.isfinite(effective).all(-1) & (effective>=0).all(-1)
    live = valid & usable_weight & (effective>0).any(-1)
    zero = valid & usable_weight & (effective==0).all(-1)''')
    out[p] = replace(out[p], 'positive_weight_observation_samples=int(live.sum()), valid_fraction=float(valid.mean()) if valid.size else None,',
                     '''positive_weight_observation_samples=int(live.sum()),
                zero_weight_valid_projection_samples=int(zero.sum()),
                invalid_weight_valid_projection_samples=int((valid & ~usable_weight).sum()),
                valid_fraction=float(valid.mean()) if valid.size else None,''')
    out[p] = replace(out[p], '        if clamped:\n            d = self.array(video.disps[:data[\'n\'],::GRID_STEP,::GRID_STEP])',
                     '''        # Count all active slots at the native return and immediately after Python clamp.
        full = self.array(video.disps[:data['n']])
        grid = dict(scope='ALL_PIXELS_ACTIVE_SLOT_PREFIX', active_slots=data['n'],
                    total=int(full.size), negative=int((np.isfinite(full) & (full < 0)).sum()),
                    nonfinite=int((~np.isfinite(full)).sum()),
                    float32_floor_count=int((full == np.float32(1e-5)).sum()))
        if clamped:
            d = full[:,::GRID_STEP,::GRID_STEP]''')
    out[p] = replace(out[p], "self.emit('ba_after_clamp',now,ba_id=self.ba_id,disparity=stats(d),",
                     "self.emit('ba_after_clamp',now,ba_id=self.ba_id,disparity=stats(d),full_disparity_grid=grid,")
    out[p] = replace(out[p], "self.emit('ba_after_native',now,ba_id=self.ba_id,rows=self.slots(video,0,data['n']),",
                     "self.emit('ba_after_native',now,ba_id=self.ba_id,rows=self.slots(video,0,data['n']),full_disparity_grid=grid,")

    p = 'src/slam.py'
    out[p] = 'from task004_controls import policy as task004_policy\n' + base[p]
    a = out[p].index('        task003().boundary("final_phase_1_done", self.video)\n')
    b = out[p].index('        self.printer.print("Final Global BA Done!", FontColor.TRACKER)', a)
    head, *phase2 = out[p][a:b].splitlines(keepends=True)
    out[p] = out[p][:a] + head + '        if task004_policy().final_phases == 2:\n' + ''.join('    ' + ln for ln in phase2) + out[p][b:]

    p = 'src/trajectory_filler.py'
    out[p] = replace(base[p], '        for (timestamp, image, _ , _)  in tqdm(image_stream):',
                     '        image_stream.task004_begin_filler()\n        for (timestamp, image, _ , _)  in tqdm(image_stream):')
    return out


def patched_runner(base):
    base = replace(base, '"""DROID-W RGB-only VIPER adapter. Upstream tracking, BA and filler are unchanged."""',
                   '''"""Task 004 runner candidate, based on the sealed Task 003 adapter."""

from task004_controls import policy as task004_policy, require_approved_runtime

require_approved_runtime()

from task003_observer import recorder as task003''')
    base = replace(base, '    def __getitem__(self,index):', '''    def task004_begin_filler(self):
        if self.phase is not None or self.seen != len(self) or self.fill_seen != 0:
            raise ValueError('unexpected Filler entry or incomplete tracking')
        self.phase = 'filler'
        progress(self.out,'filler',done=0,n=len(self),keyframes=self.video.counter.value)

    def __getitem__(self,index):''')
    base = replace(base, '''        result=super().backend()
        self.stream.phase='filler'
        progress(self.stream.out,'filler',done=0,n=len(self.stream),keyframes=self.video.counter.value)
        return result''', '''        if task004_policy().final_phases == 0:
            task003().boundary('final_pre', self.video)
            task003().boundary('final_ba_skipped', self.video)
            return None
        return super().backend()''')
    base = replace(base, '    setup_seed(cfg[\'setup_seed\'])', '''    active = task004_policy()
    dump(args.out/'task004_policy_receipt.json', dict(arm=active.arm, campaign=active.campaign,
         local_dwu=list(active.local_dwu), final_phases=active.final_phases,
         policy_sha256=os.environ['GAMECAM_TASK004_POLICY_SHA256']))
    setup_seed(cfg['setup_seed'])''')
    return base


def receipt(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))


def collect_history(verification):
    archive = TASK003 / 'GAMECAM_TASK003_VAL007_OBSERVATION_REVIEW.zip'
    manifest = load(TASK003 / 'FILE_SHA256_MANIFEST.json')['files']
    refs = [
        'TASK003_FINAL_REVIEW.md', 'TASK003_312_328_LOCAL_BA_TIMELINE.csv',
        'TASK003_ACTIVE_MECHANISMS_BY_STAGE.csv', 'TASK003_VAL007_INTERVAL_ANALYSIS.csv',
        'TASK003_TRACE_PROCESSING.json', 'TASK003_EXPORTED_RPE_OFFSETS.csv', 'EXECUTION_LOG.md',
        'remote/incoming/native_config.yaml', 'remote/incoming/task003_run_segment.py',
        'remote/incoming/task003_observer.py', 'remote/incoming/TASK003_INSTRUMENTATION_PATCH.diff',
        'remote/incoming/PATCH_VERIFICATION.json', 'remote/capture/attempt.json',
        'remote/capture/native_config.yaml', 'remote/capture/resource_samples.csv',
        'remote/capture/observer.jsonl', 'evidence/CONFIG_EFFECTIVE_DIFF.json',
        'evidence/TASK003_FINAL_PREFLIGHT.json', 'evidence/POSTRUN_ASSET_PRESERVATION.json',
        'evidence/TASK003_TARGET_EVENT_CROSSCHECK.json', 'evidence/TASK003_RUNTIME_EVALUATION.json',
    ]
    local, archive_checked = {}, []
    with zipfile.ZipFile(archive) as z:
        check(z.testzip() is None, 'Task 003 sealed archive CRC error')
        names = set(z.namelist())
        for rel in refs:
            local[rel] = r = receipt(TASK003 / rel)
            check(all(r[k] == manifest[rel][k] for k in ('sha256', 'bytes')), 'Task 003 manifest mismatch: ' + rel)
            if rel in names:
                check(sha(z.read(rel)) == r['sha256'], 'Task 003 zip/local mismatch: ' + rel)
                archive_checked.append(rel)

    sealed = (INCOMING / 'native_config.yaml').read_bytes()
    actual = (CAPTURE / 'native_config.yaml').read_bytes()
    c = load(TASK003 / 'evidence/CONFIG_EFFECTIVE_DIFF.json')
    check(sha(sealed) == c['sealed_sha256'] == control.R2_CONFIG_SHA256 and sha(actual) == c['actual_sha256'],
          'sealed YAML identity')
    def no_io(data):
        return re.sub(rb'(?m)^  (input_folder|output): [^\r\n]*', rb'  \1: <I/O>', data)
    check(no_io(sealed) == no_io(actual) and set(c['changes']) == {'data.input_folder', 'data.output'},
          'algorithm values changed in actual Task 003 YAML')

    with (CAPTURE / 'resource_samples.csv').open(encoding='utf-8', newline='') as f:
        samples = list(csv.DictReader(f))
    run = load(CAPTURE / 'attempt.json')
    check(run['status'] == 'COMPLETE_NATIVE_OUTPUT' and run['exit_code'] == 0 and run['attempts_consumed'] == 1,
          'Task 003 completion not verified')
    check(run['trace_sha256'] == local['remote/capture/observer.jsonl']['sha256'], 'historical observer identity')
    proof = load(RERUN)
    history = dict(archive=receipt(archive), crc_pass=True, archives_compared=archive_checked,
                   historical_files=local, source_binding=verification['hash_binding'],
                   algorithm_yaml_bytes_identical_after_io_redaction=True,
                   historical_usage=dict(
                       runtime_s=run['elapsed_s'], trace_bytes=run['trace_bytes'],
                       gpu_device_peak_sample_mib=max(int(s['gpu_used_mib']) for s in samples),
                       gpu_allocated_peak_bytes=run['model']['gpu_torch_peak_allocated_bytes'],
                       gpu_reserved_peak_bytes=run['model']['gpu_torch_peak_reserved_bytes'],
                       cgroup_peak_sample_bytes=max(int(s['cgroup_memory_bytes']) for s in samples),
                       shm_peak_sample_consumed_bytes=int(proof['shm_free_bytes'])-min(int(s['shm_free_bytes']) for s in samples),
                       preflight_data_free_bytes=proof['disk_free_bytes'], preflight_shm_free_bytes=proof['shm_free_bytes'],
                       preflight_gpu_free_mib=int(proof['gpu']['memory.free'])))
    write_json(ROOT / 'evidence/HISTORICAL_INPUTS.json', history)
    write(ROOT / 'candidates/r2_sealed_config.yaml', sealed)
    print(f"Task 003: CRC PASS, {len(local)} local SHA matches, {len(archive_checked)} verified corresponding ZIP entries")


def matrix():
    # Each screening arm runs once. Order is sealed before observing any screening outcomes.
    order = ['E3', 'E4', 'E7', 'E0', 'E8', 'E6', 'E1', 'E2']
    with StringIO(newline='') as f:
        w = csv.writer(f)
        w.writerow(('arm','D','W','U','screening_slot','seed','policy_file','policy_sha256','status'))
        for arm, factors in control.FACTORIAL.items():
            p = save_policy('FACTORIAL', arm, factors, 2)
            w.writerow((arm,*factors,order.index(arm)+1,43,p.relative_to(ROOT).as_posix(),digest(p),'CPU_REVIEW_ONLY'))
        write(ROOT / 'TASK004_FACTORIAL_MATRIX.csv', f.getvalue())
    for arm, phases in control.FINAL.items():
        save_policy('E5_FINAL', arm, control.FACTORIAL['E0'], phases)
    print('Generated 8 factorial and 3 Final BA review policies')


def save_policy(campaign, arm, factors, phases):
    doc = dict(schema=control.SCHEMA,base_config_sha256=control.R2_CONFIG_SHA256,
               campaign=campaign,arm=arm,local_dwu=list(factors),final_phases=phases)
    control.parse_policy(doc)
    p = ROOT / 'policies' / f'{arm}.json'
    write_json(p, doc)
    return p


def main():
    check(os.environ.get('CUDA_VISIBLE_DEVICES', '') == '', 'GPU visibility must be disabled')
    verification = load(INCOMING / 'PATCH_VERIFICATION.json')
    lock = load(TASK001 / 'evidence/SOURCE_IDENTITY_VERIFICATION.json')
    check(lock['status'] == 'PASS' and not (SOURCE / '.git').exists(), 'Task 001 source lock')
    tree = load(SOURCE_TREE)
    check(tree['sha'] == COMMIT and tree['truncated'] is False, 'frozen tree pin')
    collect_history(verification)
    inputs = verification['file_hashes']
    watched = [row['path'] for row in inputs if row['before_sha256']] + [
        'src/lib/droid.cpp', 'src/lib/droid_kernels.cu', 'src/backend.py',
        'src/utils/mono_priors/metric_depth_estimators.py', 'src/utils/mono_priors/img_feature_extractors.py']
    pinned = {r['path']: r['sha'] for r in tree['tree'] if r['type'] == 'blob'}
    source_evidence = {}
    for rel in watched:
        path = SOURCE / rel
        data = path.read_bytes()
        git_blob = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        check(git_blob == pinned[rel], 'pinned Git blob mismatch: ' + rel)
        source_evidence[rel] = dict(**receipt(path), git_blob_sha1=git_blob)

    hist_patch = INCOMING / 'TASK003_INSTRUMENTATION_PATCH.diff'
    with tempfile.TemporaryDirectory(prefix='patchcheck-', dir=ROOT) as td:
        work = Path(td) / 'work'
        work.mkdir()
        for row in inputs:
            rel, expected = row['path'], row['before_sha256']
            if expected:
                raw = (SOURCE / rel).read_bytes()
                check(sha(raw) == expected, 'Task 003 patch preimage mismatch ' + rel)
                write(work / rel, raw)
        git_apply(work, hist_patch)
        base = {}
        for row in inputs:
            rel = row['path']
            raw = (work / rel).read_bytes()
            check(sha(raw) == row['after_sha256'], 'Task 003 patch postimage mismatch ' + rel)
            check(b'\r\n' not in raw, 'Unexpected CRLF in sealed source ' + rel)
            base[rel] = raw.decode('utf-8')
        out = patched_sources(base)
        changed = {rel for rel in out if out[rel] != base[rel]}
        check(changed == {'src/frontend.py','src/factor_graph.py','src/depth_video.py','src/slam.py',
                          'src/trajectory_filler.py','task003_observer.py'}, 'candidate touched unintended files')
        extra = (ROOT / 'candidates/task004_controls.py').read_text(encoding='utf-8')
        patch = ROOT / 'candidates/TASK004_ON_TASK003.diff'
        write(patch, ''.join(diff(base[rel], out[rel], rel) for rel in sorted(changed)) +
              diff('', extra, 'task004_controls.py').replace('--- a/task004_controls.py', '--- /dev/null', 1))
        git_apply(work, patch)
        out['task004_controls.py'] = extra
        for rel, text in out.items():
            check((work / rel).read_bytes() == text.encode('utf-8'), 'Task 004 patch application mismatch: ' + rel)
            ast.parse(text, filename=rel)
            if rel in changed:
                write(ROOT / 'candidates/preview' / rel, text)

    old_runner = (INCOMING / 'task003_run_segment.py').read_text(encoding='utf-8')
    runner = patched_runner(old_runner)
    runner_file = ROOT / 'candidates/task004_run_segment.py'
    ast.parse(runner, filename=runner_file.name)
    write(runner_file, runner)
    write(ROOT / 'candidates/TASK004_RUNNER_REFERENCE_DIFF.diff', diff(old_runner, runner, 'task003_run_segment.py'))
    matrix()
    write_json(ROOT / 'evidence/SOURCE_AND_CANDIDATE_IDENTITY.json', dict(
        upstream_commit=COMMIT, source_path=str(SOURCE), verified_source_blobs=source_evidence,
        task003_patch=receipt(hist_patch), task003_postimages={rel: sha(s.encode()) for rel,s in base.items()},
        task004_postimages={rel: sha(s.encode()) for rel,s in out.items()}, changed=sorted(changed),
        patched_candidate_runner=receipt(runner_file), native_extension_modified=False,
        original_source_unchanged=all(digest(SOURCE / rel) == r['sha256'] for rel,r in source_evidence.items())))
    print(f'Git apply --check and exact postimages verified: {len(base)} Task 003, {len(out)} Task 004; {len(watched)} frozen blobs')


if __name__ == '__main__':
    main()
