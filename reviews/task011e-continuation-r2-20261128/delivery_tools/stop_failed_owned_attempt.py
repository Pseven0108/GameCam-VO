"""Stop only a positively identified, failed R2 driver; never retries it."""
import json, runpy, subprocess
from pathlib import Path

BASE=Path(__file__).resolve().parent
CODE=r'''
import json, os, signal, time
from pathlib import Path
root=Path('/root/rivermind-data/GAMECAM_TASK011E_FAST_20261128_R2')
task=root/'repo/experiments/TASK011E'
driver=str(task/'native_driver.py')
key='s43_val_038_00448-00511_A4'
ledger=task/'execution_ledger'/key
err=(ledger/'stderr.txt').read_text()
assert 'SECONDARY_THRESHOLD_PROPOSALS.csv' in err and 'FileNotFoundError' in err
assert '/TASK011B/scripts/common.py' in err
assert not (ledger/'TERMINAL.json').exists()
run=task/'runs/43/val_038_00448-00511/A4'
assert not (run/'CHILD_ENTERED.json').exists(), 'Tracking entered: re-evaluate instead of stopping blindly'
assert not (run/'native_ba_calls.jsonl').exists()
targets=[]
for proc in Path('/proc').glob('[0-9]*'):
    try:
        args=proc.joinpath('cmdline').read_bytes().decode().split('\0')
        if driver not in args:continue
        pid=int(proc.name)
        assert args[args.index('--job-key')+1]==key
        assert args[args.index('--window')+1]=='val_038_00448-00511'
        assert args[args.index('--arm')+1]=='A4'
        targets.append(dict(pid=pid,argv=args,stat=proc.joinpath('stat').read_text()))
    except FileNotFoundError:continue
assert len(targets)==1, 'Must identify exactly one owned failed native driver'
receipt=dict(status='SUPERVISOR_STOPPING_FAILED_OWNED_DRIVER',reason='SPAWN_COMMON_MODULE_COLLISION_BEFORE_TRACKING',
             tracking_entered=False,native_BA_calls=0,automatic_retry=False,targets=targets,when_unix=time.time())
path=root/'SUPERVISOR_STOP_RECEIPT.json'
assert not path.exists()
path.write_text(json.dumps(receipt,indent=2)+'\n')
for target in targets:
    proc=Path('/proc')/str(target['pid'])
    assert proc.joinpath('stat').read_text().split()[21]==target['stat'].split()[21]
    assert driver in proc.joinpath('cmdline').read_bytes().decode().split('\0')
    os.kill(target['pid'],signal.SIGTERM)
print(json.dumps(dict(status='SIGTERM_SENT_TO_FAILED_OWNED_DRIVER',pids=[t['pid'] for t in targets],
                     no_other_processes_signalled=True,no_retry=True)))
'''

def main():
    api=runpy.run_path('D:/aaa/GameCam-VO-TASK011E/experiments/TASK011E/monitor_remote.py')
    p=subprocess.run(api['command'](CODE),capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
    (BASE/'SUPERVISOR_STOP_STDOUT.txt').write_bytes(p.stdout)
    (BASE/'SUPERVISOR_STOP_STDERR.txt').write_bytes(p.stderr)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace')[-2500:])
    print(p.stdout.decode())

if __name__=='__main__':main()
