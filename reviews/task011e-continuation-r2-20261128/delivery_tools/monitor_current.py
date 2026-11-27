"""Pinned read-only R2 observation; never launches, retries or stops a job."""
import datetime, json, runpy, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = Path('D:/aaa/GameCam-VO-TASK011E/experiments/TASK011E/monitor_remote.py')

def main():
    api = runpy.run_path(str(OLD))
    code = api['CODE'].replace('GAMECAM_TASK011E_FAST_20261128_R1', 'GAMECAM_TASK011E_FAST_20261128_R2')
    p = subprocess.run(api['command'](code), capture_output=True, timeout=45,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace')[-2000:])
    data = json.loads(p.stdout)
    target = BASE / 'progress'
    target.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (target / (stamp+'.json')).write_bytes(p.stdout)
    (BASE / 'LATEST_PROGRESS.json').write_bytes(p.stdout)
    pointer = Path('D:/aaa/GameCam-VO/experiments/TASK011E_CURRENT_STATUS.json')
    state = json.loads(pointer.read_text(encoding='utf-8'))
    state.update(complete_caches=sum(x['complete'] for x in data['caches']),
                 preserved_cache_frames=sum(x['frames'] for x in data['caches']),
                 E2E_attempted=data['E2E_attempts'], E2E_terminal=data['E2E_terminal'],
                 disk_free_bytes=data['disk_free_bytes'], last_verified_unix=data['when_unix'])
    pointer.write_text(json.dumps(state, indent=2)+'\n', encoding='utf-8')
    if '--compact' in sys.argv:
        data = dict(when_unix=data['when_unix'], complete_caches=state['complete_caches'],
                    cache_inflight=[x for x in data['caches'] if not x['complete']],
                    E2E_attempted=data['E2E_attempts'], E2E_terminal=data['E2E_terminal'],
                    checkpoint=data.get('BATCH_CHECKPOINT.json'),
                    stopped=data.get('BATCH_STOPPED.json'), terminal=data.get('BATCH_TERMINAL.json'),
                    canary=data.get('CANARY_ENGINEERING_HEALTH.json'),
                    disk_free_GiB=data['disk_free_bytes']/1024**3, gpu=data['gpu'],
                    latest_job=data.get('latest_job'), service_tail=data['service_log'][-800:])
    print(json.dumps(data, ensure_ascii=True, indent=2))

if __name__ == '__main__':
    main()
