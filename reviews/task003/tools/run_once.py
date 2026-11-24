"""Launch and supervise the single authorized Task 003 process."""
import csv
import fcntl
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import ProxyHandler, build_opener

from stage_remote import (ROOT, CODE, INPUT, HOST, ORIGIN, UPLOAD, SEGMENT, COMMIT,
                          LOCKED, PIPE, check, digest, read, require, unique_json)

GIB = 1024**3
ENV = Path('/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild')
EVIDENCE = ROOT / 'evidence'
OUT = ROOT / 'results' / SEGMENT / 'attempt_001'
TRACE = OUT / 'observer.jsonl'
BOOT = Path('/proc/sys/kernel/random/boot_id')
CG = Path('/sys/fs/cgroup')
GPU_QUERY = 'index,name,uuid,memory.total,memory.used,memory.free,utilization.gpu,driver_version,compute_cap'
VIEWER_PORTS = (9875, 9876, 9877)


def utc():
    return datetime.now(timezone.utc).isoformat()


def gpu():
    out = subprocess.check_output(['nvidia-smi', f'--query-gpu={GPU_QUERY}', '--format=csv,noheader,nounits'],
                                  text=True, timeout=8)
    rows = [[col.strip() for col in row] for row in csv.reader(out.splitlines())]
    require(len(rows) == 1 and len(rows[0]) == len(GPU_QUERY.split(',')), 'Expected exactly one visible GPU')
    return dict(zip(GPU_QUERY.split(','), rows[0]))


def cgroup(name):
    p = CG / name
    return p.read_text().strip() if p.is_file() else None


def viewer_pid():
    doc = read(EVIDENCE / 'RERUN_REMOTE_START.json')
    pid = doc['pid']
    argv = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    require(doc['hostname'] == HOST and os.fsencode(ENV / 'bin/rerun') in argv, 'Rerun PID/identity drift')
    return pid


def viewer_check():
    pid = viewer_pid()
    for port in VIEWER_PORTS:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            pass
    with build_opener(ProxyHandler({})).open('http://127.0.0.1:9876/', timeout=3) as r:
        require(r.status == 200, 'Native Rerun viewer HTTP failed')
    return pid


def preflight():
    require(socket.gethostname() == HOST, 'Unexpected SSH target')
    stage = read(EVIDENCE / 'STAGE_VERIFICATION.json')
    boot = BOOT.read_text().strip()
    require(stage['boot_id'] == boot and stage['source_commit'] == COMMIT and stage['image_count'] == 487,
            'Staging boot, source or input identity mismatch')
    smoke = read(UPLOAD / 'RERUN_BROWSER_ADMISSION.json')
    require(smoke['visible_synthetic_entities'] is True and smoke['http'] == 200 and smoke['ws_bytes'] > 0
            and time.time() - smoke['checked_unix'] < 90, 'Browser render gate missing or stale')
    require(smoke['recording_id'] == read(EVIDENCE / 'RERUN_SMOKE_EMISSION.json')['recording_id'], 'Wrong browser smoke record')
    # Repeat the read-only checks on small copied assets immediately before launch.
    sources = [check(Path(row['path']), row['sha256']) for row in stage['patched_hashes']]
    sealed = check(UPLOAD / 'native_config.yaml', LOCKED['native_config.yaml'])
    manifest = check(INPUT / 'INPUT.json', LOCKED['INPUT.json'])
    extension = check(Path(stage['staged_extension']['path']), stage['staged_extension']['sha256'])
    p = ROOT / 'pipeline'
    others = {**PIPE, 'task003_run_segment.py': LOCKED['task003_run_segment.py']}
    pipeline = [check(p / path, sha) for path, sha in others.items()]
    dev = gpu()
    require(dev['name'] == 'NVIDIA GeForce RTX 3090' and dev['index'] == '0' and int(dev['memory.total']) == 24576
            and dev['compute_cap'] == '8.6' and int(dev['memory.used']) <= 768 and int(dev['memory.free']) >= 23000,
            f'GPU gate failed: {dev}')
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True, timeout=8).strip()
    require(not apps, 'Unrelated active compute process')
    disk = shutil.disk_usage(ROOT)
    shm = shutil.disk_usage('/dev/shm')
    require(disk.free >= 10*GIB and shm.free >= 8*GIB, 'Data disk or shared memory below the admitted threshold')
    pid = viewer_check()
    return dict(status='PASS_BEFORE_MODEL', checked_utc=utc(), hostname=HOST, boot_id=boot, gpu=dev,
        other_compute_processes=apps, shm_free_bytes=shm.free, disk_free_bytes=disk.free, memory_max=cgroup('memory.max'),
        memory_events=cgroup('memory.events'), viewer_pid=pid, viewer_ports=VIEWER_PORTS, browser=smoke,
        source_commit=COMMIT, sealed_config=sealed, manifest=manifest, extension=extension, patch_postimages=sources,
        pipeline=pipeline, staged_identity_sha256=digest(EVIDENCE / 'STAGE_VERIFICATION.json'), gt_uploaded=0)


def optional_json(path):
    return read(path) if path.is_file() else {}


def stop(proc):
    if proc is not None and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def launch():
    require(not (ROOT / 'ONE_RUN_CLAIM').exists() and not OUT.exists(), 'Attempt already claimed or output exists')
    pf = preflight()
    unique_json(EVIDENCE / 'TASK003_FINAL_PREFLIGHT.json', pf)
    exe = ENV / 'bin/python'
    argv = [str(exe), '-B', str(ROOT / 'pipeline/task003_run_segment.py'), str(INPUT / 'INPUT.json'), str(OUT),
            '--weights', str(ORIGIN / 'data/droid.pth')]
    custom = dict(CUDA_VISIBLE_DEVICES='0', PYTHONPATH=f'{ROOT}/pipeline:{CODE}',
        PATH=f'{ENV}/bin:' + os.environ['PATH'], PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
        OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', MPLBACKEND='Agg',
        TORCH_HOME=str(ORIGIN / 'data/torch_hub'), HF_HOME=str(ORIGIN / 'data/huggingface'), HF_HUB_OFFLINE='1',
        XDG_CACHE_HOME=str(ROOT / 'runtime_cache'), GAMECAM_TASK003_SEALED_CONFIG=str(UPLOAD / 'native_config.yaml'),
        GAMECAM_TASK003_OBSERVER_JSONL=str(TRACE))
    env = dict(os.environ, **custom)
    OUT.mkdir(parents=True)
    unique_json(OUT / 'runtime_command.json', dict(argv=argv, cwd=str(CODE), overrides=custom))
    state, model = {}, {}
    proc = None
    why = None
    first = time.monotonic()
    started = time.time()
    with (OUT/'run.log').open('xb') as output, (OUT/'resource_samples.csv').open('x', newline='') as metrics:
        writer = csv.writer(metrics)
        writer.writerow(['utc','elapsed_s','phase','frames','keyframes','gpu_used_mib','gpu_free_mib','gpu_pct',
                         'shm_free_bytes','disk_free_bytes','cgroup_memory_bytes','viewer_frumstums','trace_bytes'])
        with (ROOT/'ONE_RUN_CLAIM').open('x', encoding='ascii') as lock:
            lock.write(f'{utc()}\n{COMMIT}\n{SEGMENT}\n')
            lock.flush()
            os.fsync(lock.fileno())
        try:
            proc = subprocess.Popen(argv, cwd=CODE, env=env, stdout=output, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
            unique_json(OUT/'LAUNCH_RECEIPT.json', dict(utc=utc(), model_process_started=True, attempts_consumed=1,
                        attempts_authorized=1, pid=proc.pid, commit=COMMIT, segment=SEGMENT, input_frames=487))
            print(f'MODEL STARTED pid={proc.pid}; one attempt consumed', flush=True)
            while proc.poll() is None:
                state = optional_json(OUT/'progress.json')
                phase = state.get('phase', 'startup')
                sent = optional_json(OUT/'native_camera_stream.json').get('frustum_messages', 0)
                dev = gpu()
                disk = shutil.disk_usage(ROOT).free
                shm = shutil.disk_usage('/dev/shm').free
                metrics.flush()
                writer.writerow([utc(), round(time.monotonic()-first,3), phase,state.get('done'),state.get('keyframes'),
                                 dev['memory.used'],dev['memory.free'],dev['utilization.gpu'],shm,disk,cgroup('memory.current'),
                                 sent, TRACE.stat().st_size if TRACE.exists() else 0])
                metrics.flush()
                viewer_pid()
                if (EVIDENCE/'RERUN_ABORT_REQUEST.json').is_file():
                    why = 'BROWSER_RERUN_FAILURE'
                    break
                if not sent and phase in {'final_ba', 'filler'}:
                    why = 'NATIVE_RERUN_NO_FRUSTUM_BEFORE_FINAL_STAGES'
                    break
                if disk < 4 * GIB:
                    why = 'LOW_DISK_DURING_ATTEMPT'
                    break
                if time.time()-state.get('time_unix', started) > (900 if phase in {'startup','model_init','tracking'} else 3600):
                    why = 'NO_PROGRESS_TIMEOUT'
                    break
                time.sleep(2)
        except (Exception, KeyboardInterrupt) as exc:
            why = f'{type(exc).__name__}: {exc}'
        finally:
            stop(proc)
    code = proc.returncode if proc is not None else None
    model = optional_json(OUT/'model_result.json')
    state = optional_json(OUT/'progress.json')
    ok = (code == 0 and why is None and model.get('valid_poses') == 487 and model.get('filler_frames') == 487
          and model.get('read_frames') == 487 and model.get('native_viewer_exit') == 0
          and model.get('native_camera_messages', 0) > 0 and (OUT/'trajectory.npz').is_file()
          and model.get('trajectory_sha256') == digest(OUT/'trajectory.npz'))
    result = dict(status='COMPLETE_NATIVE_OUTPUT' if ok else ('MODEL_FAILED' if proc is not None else 'PROCESS_NOT_STARTED'),
                  exit_code=code, error=why, attempts_consumed=int(proc is not None), attempts_authorized=1,
                  started_unix=started, end_utc=utc(), elapsed_s=round(time.monotonic()-first,3), model=model,
                  progress=state, memory_events_after=cgroup('memory.events'), trace_bytes=TRACE.stat().st_size if TRACE.is_file() else 0,
                  trace_sha256=digest(TRACE) if TRACE.is_file() else None, retried=False)
    unique_json(OUT/'attempt.json', result)
    print(result, flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    with (ROOT/'gpu.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raise SystemExit(launch())
