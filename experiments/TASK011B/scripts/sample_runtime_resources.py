"""Read-only sampled resource evidence; never changes GPU allocation or jobs."""
import datetime,json,shlex,subprocess,time
from pathlib import Path
from common import TASK,dump
from remote_transport import SSH,options

REMOTE='/root/rivermind-data/GAMECAM_TASK011B_20261127_AMP_NATIVE_R2'


def main():
    out=TASK/'private/runtime_resource_samples_001.jsonl'
    if out.exists():raise FileExistsError('Preserve earlier sampling session')
    code='''import json,subprocess,shutil,datetime
from pathlib import Path
r=Path(ROOT)
def query(args):
 p=subprocess.run(args,capture_output=True,text=True)
 return dict(code=p.returncode,stdout=p.stdout,stderr=p.stderr)
running=[]
for p in sorted((r/'job_receipts').glob('*.json')):
 x=json.loads(p.read_text())
 if x['status'] in ('RUNNING','STARTED'):running.append(dict(label=p.stem,**x))
print(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 running=running,data_free_bytes=shutil.disk_usage(r).free,
 shm_free_bytes=shutil.disk_usage('/dev/shm').free,
 gpu=query(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.free','--format=csv,noheader,nounits']),
 compute=query(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits']))))
'''.replace('ROOT',repr(REMOTE))
    while not (TASK/'gpu_results/BATCH_COMPLETE.json').exists():
        p=subprocess.run([str(SSH),'-T','-p','31454',*options(),
            'root@sc01-ssh.gpuhome.cc','/usr/bin/python3 -c '+shlex.quote(code)],
            capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode:
            row=dict(local_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                sample_failed=True,exit_code=p.returncode)
        else:row=json.loads(p.stdout)
        with out.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        time.sleep(20)
    dump(TASK/'private/RUNTIME_RESOURCE_SAMPLING_STATUS.json',dict(
        status='COMPLETE',path=str(out),sample_seconds=20,
        sampled_peaks_are_lower_bounds=True,first_6_runs_not_covered=True,
        GPU_total_includes_preexisting_driver_reported_allocation=True,
        no_process_killed=True,no_device_reset=True))
    print('RUNTIME_RESOURCE_SAMPLING_COMPLETE',flush=True)


if __name__=='__main__':main()
