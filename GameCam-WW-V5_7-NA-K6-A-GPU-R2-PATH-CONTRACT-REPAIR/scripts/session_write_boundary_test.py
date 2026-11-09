"""Real child-process Session Write Boundary integration test.

This test installs the audit hook in a fresh subprocess and exercises the
exact worker telemetry/control-file contract. It never imports torch and never
loads a checkpoint.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


def secure_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = -1
            f.write(text)
    finally:
        if fd != -1:
            os.close(fd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="k6a-session-boundary-", dir=str(output.parent)))
    session = "K6A_BOUNDARY_" + str(os.getpid()) + "_" + str(time.time_ns())
    session_dir = work / "session"
    out = session_dir / "model"
    session_dir.mkdir(mode=0o700)
    out.mkdir(mode=0o700)
    controls = {
        "work.permit.json": {"session": session, "execution_kind": "cpu_dummy", "model_execution_authorized": False},
        "nvml.latest.json": {"kind": "nvml", "session": session, "ok": True},
        "supervisor_heartbeat.jsonl": "heartbeat\n",
        "authorization.claim.json": "claim\n",
        "supervisor_stop.json": "stop\n",
        "nvml_samples.jsonl": "sample\n",
        "monitor.stop": "stop\n",
    }
    for name, value in controls.items():
        secure_write(session_dir / name, json.dumps(value) if isinstance(value, dict) else value)
    secure_write(out / "result.json", json.dumps({"status": "READY"}))
    (out / 'preexisting-control-link').symlink_to(session_dir / 'work.permit.json')
    os.link(session_dir / 'authorization.claim.json', out / 'preexisting-control-hardlink')
    control_fd = os.open(str(session_dir), os.O_RDONLY | os.O_DIRECTORY)
    # Import the existing IPC owner implementation before installing the worker hook.
    scripts = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts))
    from ipc_runtime import IPCPolicy, cleanup_owner, prepare_owner

    owner = None
    child_result = None
    child_stderr = ""
    try:
        owner = prepare_owner(session_dir, session)
        child_code = textwrap.dedent(
            r'''
            import json, os, pathlib, sys
            scripts = pathlib.Path(sys.argv[1]); session_dir = pathlib.Path(sys.argv[2]); out = pathlib.Path(sys.argv[3]); session = sys.argv[4]; control_fd = int(sys.argv[5])
            sys.path.insert(0, str(scripts))
            from ipc_runtime import IPCPolicy
            from linux_safety import append_json, atomic_json
            from model_io_boundary_v2 import ModelIOBoundary
            policy = IPCPolicy('/dev/shm/gamecam-ipc/' + session, str(session_dir / 'tmp'), session, session_dir)
            worker_files = [session_dir/'cuda_samples.jsonl', session_dir/'cuda.latest.json', session_dir/'frame_samples.jsonl', session_dir/'ipc_worker_events.jsonl', session_dir/'worker_terminal.json']
            worker_reads = [session_dir/'work.permit.json', session_dir/'nvml.latest.json', session_dir/'supervisor_heartbeat.jsonl']
            boundary = ModelIOBoundary([], [], [scripts], [out], [], ipc_policy=policy, worker_files=worker_files, worker_read_files=worker_reads, worker_atomic_files=[session_dir/'cuda.latest.json', session_dir/'worker_terminal.json'], worker_root=session_dir)
            policy.install_arena()
            boundary.install()
            results = []
            def allow(name, fn):
                try:
                    fn(); results.append({'name': name, 'allowed': True})
                except BaseException as exc:
                    results.append({'name': name, 'allowed': False, 'error': repr(exc)})
            def reject(name, fn):
                try:
                    fn(); results.append({'name': name, 'rejected': False, 'error': 'operation unexpectedly succeeded'})
                except BaseException as exc:
                    results.append({'name': name, 'rejected': True, 'error': str(exc)})
            import multiprocessing
            allow('real_value_allocation', lambda: multiprocessing.Value('i', 3))
            allow('real_array_allocation', lambda: multiprocessing.Array('i', [1,2,3]))
            allow('worker_telemetry_append', lambda: append_json(session_dir/'cuda_samples.jsonl', {'session': session, 'sample_seq': 1}))
            allow('cuda_latest_atomic_write', lambda: atomic_json(session_dir/'cuda.latest.json', {'session': session, 'ok': True}))
            allow('worker_terminal_atomic_write', lambda: atomic_json(session_dir/'worker_terminal.json', {'session': session, 'status': 'RUN_COMPLETED'}))
            allow('model_output_atomic_write', lambda: atomic_json(out/'result.json', {'status': 'RUN_COMPLETED'}))
            allow('read_work_permit', lambda: json.loads((session_dir/'work.permit.json').read_text()))
            allow('read_nvml_latest', lambda: json.loads((session_dir/'nvml.latest.json').read_text()))
            allow('read_supervisor_heartbeat', lambda: (session_dir/'supervisor_heartbeat.jsonl').read_text())
            allow('read_ipc_marker', lambda: (policy.root/'.gamecam-session.json').read_text())
            reject('preexisting_symlink_control_write', lambda: (out/'preexisting-control-link').write_text('x'))
            reject('preexisting_hardlink_control_write', lambda: (out/'preexisting-control-hardlink').write_text('x'))
            reject('inherited_directory_fd_unlink', lambda: os.unlink('authorization.claim.json', dir_fd=control_fd))
            reject('inherited_directory_fd_open', lambda: os.open('authorization.claim.json', os.O_WRONLY|os.O_TRUNC, dir_fd=control_fd))
            reject('delete_authorization_claim', lambda: os.unlink(session_dir/'authorization.claim.json'))
            reject('overwrite_supervisor_heartbeat', lambda: (session_dir/'supervisor_heartbeat.jsonl').write_text('x'))
            reject('overwrite_nvml_samples', lambda: (session_dir/'nvml_samples.jsonl').write_text('x'))
            reject('overwrite_supervisor_stop', lambda: (session_dir/'supervisor_stop.json').write_text('x'))
            reject('overwrite_monitor_stop', lambda: (session_dir/'monitor.stop').write_text('x'))
            reject('delete_worker_terminal', lambda: os.unlink(session_dir/'worker_terminal.json'))
            reject('append_log_atomic_replace', lambda: atomic_json(session_dir/'cuda_samples.jsonl', {'x': 1}))
            reject('foreign_pid_temp', lambda: (session_dir/('cuda.latest.json.'+str(os.getpid()+1)+'.tmp')).write_text('x'))
            reject('output_to_control_rename', lambda: os.replace(out/'result.json', session_dir/'cuda.latest.json'))
            reject('foreign_pid_arena', lambda: os.open(session_dir/'tmp'/('pym-'+str(os.getpid()+1)+'-abcdefgh'), os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600))
            reject('nested_fallback_write', lambda: (session_dir/'tmp'/'nested'/'file.txt').write_text('x'))
            reject('chown_control', lambda: os.chown(session_dir/'work.permit.json', os.getuid(), os.getgid()))
            reject('unlink_via_dirfd', lambda: os.unlink('authorization.claim.json', dir_fd=os.open(str(session_dir), os.O_RDONLY|os.O_DIRECTORY)))
            reject('open_via_dirfd', lambda: os.open('authorization.claim.json', os.O_WRONLY|os.O_TRUNC, dir_fd=os.open(str(session_dir), os.O_RDONLY|os.O_DIRECTORY)))
            reject('direct_overwrite_work_permit', lambda: (session_dir/'work.permit.json').open('w').write('x'))
            reject('direct_overwrite_nvml_latest', lambda: (session_dir/'nvml.latest.json').open('w').write('x'))
            reject('direct_append_atomic_cuda_latest', lambda: (session_dir/'cuda.latest.json').open('a').write('x'))
            reject('direct_overwrite_cuda_samples', lambda: (session_dir/'cuda_samples.jsonl').open('w').write('x'))
            reject('write_authorization_claim', lambda: (session_dir/'authorization.claim.json').open('w').write('x'))
            reject('write_arbitrary_session_root', lambda: (session_dir/'arbitrary.txt').open('w').write('x'))
            reject('write_fallback_arbitrary', lambda: (session_dir/'tmp'/'arbitrary.txt').open('w').write('x'))
            reject('read_arbitrary_session_root', lambda: (session_dir/'authorization.claim.json').read_text())
            reject('remove_work_permit', lambda: os.remove(session_dir/'work.permit.json'))
            reject('mkdir_session_root', lambda: os.mkdir(session_dir/'nested'))
            reject('chmod_session_control', lambda: os.chmod(session_dir/'authorization.claim.json', 0o600))
            reject('hard_link_escape', lambda: os.link(out/'result.json', session_dir/'hard-link'))
            reject('symlink_escape', lambda: os.symlink(str(out/'result.json'), str(session_dir/'symbolic-link')))
            reject('rename_session_escape', lambda: os.rename(session_dir/'authorization.claim.json', out/'escaped.txt'))
            reject('foreign_ipc_session', lambda: (pathlib.Path('/dev/shm/gamecam-ipc/FOREIGN_SESSION_20261109')/'.gamecam-session.json').read_text())
            child_result = {'child_pid': os.getpid(), 'status': 'PASS' if all(x.get('allowed', False) for x in results if 'allowed' in x) and all(x.get('rejected', False) for x in results if 'rejected' in x) else 'FAIL', 'tests': results, 'denied_events': boundary.events, 'worker_root': str(session_dir), 'output_root': str(out), 'model_execution_authorized': False, 'checkpoint_deserialized': False, 'tracker_constructed': False, 'tracker_run_called': False, 'real_ba_executed': False, 'GT_values_read': False}
            print(json.dumps(child_result, ensure_ascii=False), flush=True)
            raise SystemExit(0 if child_result['status'] == 'PASS' else 2)
            '''
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(scripts)
        cmd = [sys.executable, "-c", child_code, str(scripts), str(session_dir), str(out), session, str(control_fd)]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60, pass_fds=(control_fd,))
        child_stderr = proc.stderr
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if lines:
            child_result = json.loads(lines[-1])
        else:
            child_result = {"status": "FAIL", "error": "child emitted no JSON", "stdout": proc.stdout}
        child_result["child_returncode"] = proc.returncode
        child_result["child_stderr"] = proc.stderr
        cleanup = cleanup_owner(owner, True, True, [child_result.get('child_pid')])
        child_result["ipc_cleanup"] = cleanup
        child_result["status"] = "PASS" if child_result.get("status") == "PASS" and proc.returncode == 0 and cleanup.get("passed") else "FAIL"
    except BaseException as exc:
        child_result = {"status": "FAIL", "error": str(exc), "traceback": __import__('traceback').format_exc(), "model_execution_authorized": False, "checkpoint_deserialized": False, "tracker_constructed": False, "tracker_run_called": False, "real_ba_executed": False, "GT_values_read": False}
    finally:
        os.close(control_fd)
        shutil.rmtree(work, ignore_errors=True)
    output.write_text(json.dumps(child_result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": child_result.get("status"), "tests": len(child_result.get("tests", [])), "output": str(output)}))
    return 0 if child_result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
