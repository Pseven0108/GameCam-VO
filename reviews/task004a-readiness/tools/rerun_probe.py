"""Exercise the pinned Rerun release with synthetic data and software rendering."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from urllib.request import ProxyHandler, build_opener

from contracts import PORTS, need, new_json, read_json, stat_sha, utc


def emit(recording, port, sdk_root):
    import numpy as np
    import rerun as rr
    import rerun.blueprint as rrb
    import rerun_bindings

    sdk_root = Path(sdk_root).resolve(strict=True)
    distribution = importlib.metadata.distribution('rerun-sdk')
    need(distribution.version == rr.__version__ == '0.22.1'
         and Path(distribution.locate_file('')).resolve() == sdk_root
         and Path(rr.__file__).resolve().is_relative_to(sdk_root/'rerun_sdk')
         and Path(rerun_bindings.__file__).resolve().is_relative_to(sdk_root/'rerun_bindings'),
         'Rerun imports do not come from the pinned wheel')
    rr.init('task004a_cpu_probe', recording_id=recording)
    rr.connect_tcp(f'127.0.0.1:{port}', flush_timeout_sec=4.)
    rr.send_blueprint(rrb.Blueprint(rrb.Spatial3DView(origin='world', name='Task004-A render proof')))
    rr.log('world', rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)
    rr.log('world/task004a_probe_triplet', rr.Points3D(
        np.array([[-1, 0, 0], [0, 0.65, 0], [1, 0, 0]], dtype=np.float32),
        radii=[0.24, 0.24, 0.24], colors=[[255, 0, 213], [0, 255, 34], [0, 222, 255]]), static=True, strict=True)
    rr.log('world/task004a_camera_frustum', rr.LineStrips3D(
        [[[0, -0.7, 0], [-0.45, -0.4, 0.7], [0.45, -0.4, 0.7], [0, -0.7, 0]]],
        colors=[[255, 236, 0]], radii=0.02), static=True, strict=True)
    rr.log('task004a_proof', rr.TextDocument('Task004-A synthetic probe ' + recording), static=True, strict=True)
    rr.get_global_data_recording().flush(blocking=True)
    print(json.dumps(dict(recording_id=recording, sdk=rr.__version__, sdk_module=rr.__file__,
                          bindings_module=rerun_bindings.__file__, data='SYNTHETIC_ONLY', tcp_port=port)))


def ready(port):
    with socket.create_connection(('127.0.0.1', port), timeout=0.3):
        pass


def wait_for(predicate, seconds, label):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.15)
    raise TimeoutError(label)


def listeners(process, ports):
    need(process.poll() is None, 'viewer exited before all listeners became reachable')
    try:
        for port in ports:
            ready(port)
        return True
    except OSError:
        return False


def pixel_counts(path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as pic:
        a = np.asarray(pic.convert('RGB'))
    h, w = a.shape[:2]
    a = a[int(h*.07):int(h*.73), int(w*.17):int(w*.74)]
    r,g,b = a[:,:,0], a[:,:,1], a[:,:,2]
    return dict(magenta=int(((r>215)&(g<55)&(b>145)).sum()),
                green=int(((r<55)&(g>215)&(b<85)).sum()),
                cyan=int(((r<55)&(g>160)&(b>215)).sum()),
                yellow=int(((r>220)&(g>175)&(b<70)).sum()))


def main(args):
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    tcp, http_port, ws_port = PORTS
    for port in PORTS:
        with socket.socket() as sock:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(('127.0.0.1', port))
    version = subprocess.run([args.rerun, '--version'], capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    need(version.startswith('rerun-cli 0.22.1 '), 'wrong Rerun executable')
    argv = [args.rerun, '--bind', '127.0.0.1', '--port', str(tcp), '--serve-web',
            '--web-viewer-port', str(http_port), '--ws-server-port', str(ws_port), '--server-memory-limit', '768MB']
    browser, viewer = None, None
    recording = str(uuid.uuid4())
    http = build_opener(ProxyHandler({}))
    report = dict(recording_id=recording, version=version, server_command=argv, ports=list(PORTS),
                  status='BLOCKED', checked_utc=utc(), data='SYNTHETIC_ONLY', remote=False,
                  verified_model=False, physical_gpu_requested=False)
    try:
        with (out/'rerun.stdout.txt').open('xb') as so, (out/'rerun.stderr.txt').open('xb') as se:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            viewer = subprocess.Popen(argv, stdout=so, stderr=se, creationflags=flags)
            wait_for(lambda: listeners(viewer, PORTS), 10, 'Rerun TCP/HTTP/WebSocket ports not available')
            report['listener_count'] = len(PORTS)
            with http.open(f'http://127.0.0.1:{http_port}/', timeout=5) as response:
                need(response.status == 200, 'viewer HTTP failed')
                report['http_status'] = response.status
            url = f'http://127.0.0.1:{http_port}/?url=ws%3A%2F%2F127.0.0.1%3A{ws_port}'
            with (out/'browser.stdout.txt').open('xb') as bo, (out/'browser.stderr.txt').open('xb') as be:
                js = Path(__file__).with_name('rerun_browser.mjs')
                browser = subprocess.Popen([args.node, str(js), args.chrome, str(out), url, str(ws_port)],
                                           stdout=bo, stderr=be, creationflags=flags)
                wait_for(lambda: (out/'browser_ready.json').is_file() or browser.poll() is not None,
                         23, 'browser never reached the before-data render')
                need(browser.poll() is None, 'browser exited before emitter')
                sdk_root = Path(args.sdk_root).resolve(strict=True)
                # PYTHONPATH does not process the .pth shipped in this unpacked wheel.
                sdk_path = os.pathsep.join(map(str, (sdk_root/'rerun_sdk', sdk_root)))
                env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                           PYTHONPATH=sdk_path, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
                emitted = subprocess.run([sys.executable, '-B', __file__, '--emit', recording, str(tcp), str(sdk_root)],
                                         env=env, capture_output=True, timeout=18)
                (out/'emitter.stdout.txt').write_bytes(emitted.stdout)
                (out/'emitter.stderr.txt').write_bytes(emitted.stderr)
                report['emitter_exit_code'] = emitted.returncode
                need(emitted.returncode == 0, 'synthetic SDK emission failed')
                report['browser_exit_code'] = browser.wait(timeout=26)
                need(report['browser_exit_code'] == 0, 'browser capture failed')
            transport = read_json(out/'browser_transport.json')
            before, after = (pixel_counts(out/f'browser_{phase}.png') for phase in ('before', 'after'))
            report.update(browser_transport=transport, before_pixels=before, after_pixels=after,
                          before_sha256=stat_sha(out/'browser_before.png'), after_sha256=stat_sha(out/'browser_after.png'))
            need('SwiftShader' in transport['renderer'] and transport['websocket_handshake'] == 101
                 and transport['websocket_frames'] >= 2 and transport['websocket_base64_characters'] > 0
                 and not transport['browser_errors'],
                 'software rendering or payload transport unverified')
            need(all(after[k] >= max(40, before[k] + 30) for k in ('magenta', 'green', 'cyan', 'yellow')),
                 'expected colored geometry and frustum did not visibly render')
            report['status'] = 'LOCAL_REAL_BROWSER_RENDER_PASS'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        for name, child in [('browser', browser), ('viewer', viewer)]:
            if child is not None:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                report[f'{name}_exit_after_cleanup'] = child.returncode
        new_json(out/'RERUN_LOCAL_PROBE_RESULT.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--emit', nargs=3)
    cli.add_argument('--rerun')
    cli.add_argument('--sdk-root')
    cli.add_argument('--node')
    cli.add_argument('--chrome')
    cli.add_argument('--out', type=Path)
    opt = cli.parse_args()
    if opt.emit:
        emit(opt.emit[0], int(opt.emit[1]), opt.emit[2])
    else:
        main(opt)
