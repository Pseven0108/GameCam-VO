"""Task004-A serial campaign controller. Public entry point runs only a CPU substitute."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from archive import receive_copy, seal, verify_zip
from attempt_contract import validate_attempt
from contracts import (ARM_BUDGET, COMMIT, CONFIG_SHA, DISK_ADMISSION, DISK_FLOOR, INPUT_SHA, ORDER, PORTS,
                       ROOT, SEGMENT, need, new_json, stat_sha, utc, verify_matrix, verify_policy)
from endpoints import METRIC_FIELDS, RETENTION_FIELDS, evaluate
from contracts import write_csv


def cpu_environment():
    return dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
                PYTHONNOUSERSITE='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')


def real_runtime_not_released():
    raise SystemExit('Task004-A review only: no GPU dispatch authorized or reachable in this release')


def native_launch_plan(attempt, policy, sha, lockdown):
    """Generate the future argv/environment; never execute it from this review release."""
    cfg, src, pipe, manifest = [Path(lockdown[k]) for k in ('config', 'source', 'pipeline', 'manifest')]
    python, weight = [Path(lockdown[k]) for k in ('python', 'tracker')]
    for p in (attempt, policy, cfg, src, pipe, manifest, python, weight):
        need(p.is_absolute(), f'not an absolute staged path: {p}')
    pins = lockdown['pinned_runtime_files']
    need(pins[str(cfg)] == CONFIG_SHA and pins[str(manifest)] == INPUT_SHA, 'reference input identity drift')
    for name in ('task004_run_segment.py', 'segment_input.py', 'transfer_common.py'):
        need(str(pipe/name) in pins, f'unpinned pipeline entry: {name}')
    for name in ('task004_controls.py', 'task003_observer.py', 'src/depth_video.py', 'src/frontend.py',
                 'src/factor_graph.py', 'src/slam.py', 'src/trajectory_filler.py'):
        need(str(src/name) in pins, f'unpinned patched source: {name}')
    need(str(weight) in pins and len(lockdown['weights']) == 4 and str(weight) in lockdown['weights']
         and all(p in pins for p in lockdown['weights']) and lockdown['extension'] in pins,
         'unverified checkpoint/extension inventory')
    for name, pin in pins.items():
        p = Path(name)
        need(p.is_absolute() and p.is_file() and stat_sha(p) == pin, f'staged asset SHA mismatch: {name}')
    env = dict(GAMECAM_TASK004_POLICY=str(policy), GAMECAM_TASK004_POLICY_SHA256=sha,
               GAMECAM_TASK003_SEALED_CONFIG=str(cfg), GAMECAM_TASK003_OBSERVER_JSONL=str(attempt/'observer.jsonl'),
               PYTHONPATH=os.pathsep.join([str(pipe), str(src)]), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONUNBUFFERED='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               TORCH_HOME=lockdown['torch_home'], HF_HOME=lockdown['hf_home'], HF_HUB_OFFLINE='1',
               MPLBACKEND='Agg', CUDA_VISIBLE_DEVICES='0', XDG_CACHE_HOME=str(attempt/'runtime_cache'))
    return dict(argv=[str(python), '-B', str(pipe/'task004_run_segment.py'), str(manifest), str(attempt),
                      '--weights', str(weight)], cwd=str(src), env_overrides=env, mode='REAL_PLAN_ONLY',
                commit=COMMIT, segment=SEGMENT, output_dir=str(attempt), input_dir=str(manifest.parent),
                preflight_required=True, viewer_ports=list(PORTS), real_dispatch='BLOCKED_PENDING_USER_APPROVAL')


def require_disk(free, required):
    need(type(free) is int and free >= required, f'insufficient disk: {free} < {required} bytes')


def run_campaign(root, receiving_root, assets, mock_script, gt, *, fail_arm=None, corrupt_arm=None,
                 timeout=35, free=lambda p: shutil.disk_usage(p).free):
    """Run the full serial workflow with the fixed CPU fixture; failure is terminal."""
    root, receiving_root, assets = (Path(p).resolve() for p in (root, receiving_root, assets))
    mock_script = Path(mock_script).resolve(strict=True)
    need(mock_script == ROOT/'fixtures/mock_child.py', 'only the packaged synthetic fixture may be launched')
    need(root != receiving_root and not root.is_relative_to(receiving_root) and not receiving_root.is_relative_to(root),
         'choose a distinct receiving directory outside the run root')
    need(not root.exists() and not receiving_root.exists(), 'campaign or receipt directory already exists; no resume or retry')
    verify_matrix(assets)
    config = assets/'candidates/r2_sealed_config.yaml'
    need(stat_sha(config) == CONFIG_SHA, 'R2 configuration identity drift')
    root.mkdir(exist_ok=False)
    receiving_root.mkdir(exist_ok=False)
    spool = root/'archives'
    spool.mkdir()
    campaign = 'mock-' + uuid.uuid4().hex
    new_json(root/'CAMPAIGN_CLAIM.json', dict(mode='CPU_MOCK_ONLY', id=campaign, created_utc=utc(), order=list(ORDER)))
    completed, started, failed, failure, recovery_error = [], [], None, None, None
    retention, fixed, direct = [], [], []
    for slot, arm in enumerate(ORDER, 1):
        out = None
        process = None
        launched_utc = None
        exit_code = None
        try:
            headroom = free(root)
            require_disk(headroom, DISK_ADMISSION)
            require_disk(free(receiving_root), ARM_BUDGET)
            policy = assets/'policies'/f'{arm}.json'
            sha = verify_policy(policy, arm)
            attempt = f'{slot:02d}-{arm}-{uuid.uuid4().hex[:12]}'
            out = root/attempt
            out.mkdir(exist_ok=False)
            staged_policy = out/'policy.json'
            with staged_policy.open('xb') as stream:
                stream.write(policy.read_bytes())
            verify_policy(staged_policy, arm)
            cmd = [sys.executable, '-B', str(mock_script), str(out), str(config), arm, sha]
            if fail_arm == arm:
                cmd += ['--process-failure']
            if corrupt_arm == arm:
                cmd += ['--bad-trace']
            launch = dict(mode='CPU_MOCK_ONLY', campaign=campaign, arm=arm, slot=slot, attempt_id=attempt,
                          policy_sha256=sha, config_sha256=CONFIG_SHA, input_dir='CPU_MOCK_NO_IMAGES',
                          output_dir=str(out), argv=cmd, cwd=str(mock_script.parent), started_utc=utc(),
                          cuda_visible_devices='', data_disk_free_before_bytes=headroom, previous=completed[-1] if completed else None)
            new_json(out/'LAUNCH_INTENT.json', launch)
            with (out/'process.stdout.txt').open('xb') as stdout, (out/'process.stderr.txt').open('xb') as stderr:
                launched_utc = time.monotonic()
                process = subprocess.Popen(cmd, cwd=mock_script.parent, env=cpu_environment(), stdout=stdout, stderr=stderr,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                started.append(arm)
                new_json(out/'LAUNCH_RECEIPT.json', dict(launch, pid=process.pid, model_started=False))
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    require_disk(free(root), DISK_FLOOR)
                    need(time.monotonic() < deadline, 'CPU fixture timeout')
                    time.sleep(0.05)
                exit_code = process.returncode
            new_json(out/'PROCESS_RECEIPT.json', dict(mode='CPU_MOCK_ONLY', pid=process.pid, exit_code=exit_code,
                     finished_utc=utc(), elapsed_s=round(time.monotonic()-launched_utc, 6)))
            need(exit_code == 0, f'CPU fixture exited {exit_code}')
            trace, poses, keys = validate_attempt(out, arm, sha, config)
            retained, metrics, filler, loop = evaluate(arm, attempt, trace, poses, keys, gt)
            new_json(out/'VALIDATION_RECEIPT.json', dict(status='SYNTHETIC_ONLY', trace=trace.summary(),
                     retention=retained, endpoint_metrics=metrics, filler_diagnostics=filler, local_first_last=loop))
            # Same-storage ZIP is conservative: reserve an uncompressed bound plus metadata before any write.
            spool_and_receive(out, spool, receiving_root, attempt, free)
            completed.append(arm)
            retention.append(retained)
            fixed.append(metrics[0])
            direct.append(metrics[1])
        except Exception as exc:
            failed, failure = arm, f'{type(exc).__name__}: {exc}'
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if out is not None and out.is_dir():
                new_json(out/'FAILURE.json', dict(arm=arm, error=failure, utc=utc(), model_started=False,
                         pid=process.pid if process else None, actual_exit_code=process.returncode if process else None))
                if process is not None and not (out/'PROCESS_RECEIPT.json').exists():
                    new_json(out/'PROCESS_RECEIPT.json', dict(mode='CPU_MOCK_ONLY', pid=process.pid,
                             exit_code=process.returncode, finished_utc=utc(), elapsed_s=round(time.monotonic()-launched_utc, 6)))
                if not (spool/f'{out.name}.zip').exists():
                    try:
                        spool_and_receive(out, spool, receiving_root, out.name, free)
                    except Exception as recovery:
                        recovery_error = f'{type(recovery).__name__}: {recovery}'
            break
    for arm in ORDER[len(completed):]:
        state = 'FAILED_MOCK' if arm == failed else 'NOT_RUN_AFTER_FAILURE'
        msg = failure if arm == failed else 'PREVIOUS_ARM_DID_NOT_PASS'
        retention.append(dict(arm=arm, status=state, reason=msg))
        for data, kind in ((fixed, 'FIXED_RGB_FINAL_EXPORT'), (direct, 'DIRECT_RETAINED_KEYFRAME_POST_FINAL_BA')):
            data.append(dict(arm=arm, status=state, source=kind, reason=msg))
    write_csv(root/'SYNTHETIC_ENDPOINT_RETENTION.csv', RETENTION_FIELDS, retention)
    write_csv(root/'SYNTHETIC_FIXED_RGB_ENDPOINT_METRICS.csv', METRIC_FIELDS, fixed)
    write_csv(root/'SYNTHETIC_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv', METRIC_FIELDS, direct)
    summary = dict(mode='CPU_MOCK_ONLY', id=campaign, status='MOCK_COMPLETE' if failed is None else 'STOPPED',
                   order=list(ORDER), started=started, completed=completed, failed_arm=failed, failure=failure,
                   failure_archive_error=recovery_error, gpu_runs=0, retried=False, cleanup_authorized=False)
    new_json(root/'CAMPAIGN_RESULT.json', summary)
    return summary


def spool_and_receive(out, spool, receiving_root, attempt, free):
    from archive import inventory

    files = inventory(out)
    payload = sum(f['bytes'] for f in files.values())
    zip_bound = payload + payload//100 + 4096*len(files) + 2**20
    require_disk(free(spool), DISK_FLOOR + zip_bound)
    need(payload + zip_bound <= ARM_BUDGET, 'source and spool exceed the per-arm 3 GiB reserve; require separate archive storage')
    require_disk(free(receiving_root), zip_bound)
    zipped = spool/f'{attempt}.zip'
    receipt = seal(out, zipped, attempt)
    # Same device can still be used for this mock test; account for both ZIPs before receiving.
    require_disk(free(spool), DISK_FLOOR + zip_bound)
    need(Path(spool).stat().st_dev != Path(receiving_root).stat().st_dev or payload + 2*zip_bound <= ARM_BUDGET,
         'two ZIP copies exceed the per-arm reserve on this filesystem')
    copied = receive_copy(zipped, receiving_root/zipped.name, receipt)
    verify_zip(receiving_root/zipped.name, expected_sha=receipt['sha256'], expected_attempt=attempt)
    new_json(receiving_root/f'{attempt}.verified.json', copied)
    require_disk(free(spool), DISK_FLOOR)
    return copied


if __name__ == '__main__':
    import json

    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--native', action='store_true')
    arg.add_argument('--mock-run-root', type=Path)
    arg.add_argument('--mock-receive-root', type=Path)
    options = arg.parse_args()
    if options.native:
        real_runtime_not_released()
    if options.mock_run_root is None or options.mock_receive_root is None:
        arg.error('both mock run and receiving directories are required')
    sys.path.insert(0, str(ROOT/'fixtures'))
    from mock_child import synthetic_gt

    result = run_campaign(options.mock_run_root, options.mock_receive_root, ROOT/'assets',
                          ROOT/'fixtures/mock_child.py', synthetic_gt())
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'MOCK_COMPLETE' else 2)
