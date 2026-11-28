"""Watch this one approved batch to a terminal state; never retries jobs."""
import json
from pathlib import Path
import subprocess
import sys
import time

BASE=Path(__file__).resolve().parent


def main():
    while True:
        result=subprocess.run([sys.executable,'-B',str(BASE/'monitor.py')],capture_output=True,timeout=55)
        if result.returncode:
            print(json.dumps(dict(status='OBSERVATION_ERROR',error=result.stderr.decode('utf-8','replace')[-2500:])),flush=True)
            return 2
        data=json.loads(result.stdout)
        brief={name:data.get(name) for name in ('when_unix','attempted','terminal','complete',
             'initialization_failed','engineering_failed','gpu','snapshots','snapshot_bytes')}
        brief['disk_free_GiB']=data['disk_free_bytes']/1024**3
        brief['job']=data.get('latest_job',{}).get('job_key')
        brief['stage']=data.get('CHILD_STAGE.json',{}).get('stage')
        brief['native_ba_calls']=data.get('native_ba_calls')
        for name in ('BATCH_STOPPED.json','BATCH_TERMINAL.json','CANARY_ENGINEERING_HEALTH.json'):
            if name in data:brief[name]=data[name]
        print(json.dumps(brief,ensure_ascii=True),flush=True)
        if data.get('BATCH_STOPPED.json') or data.get('BATCH_TERMINAL.json'):return 0
        time.sleep(40)


if __name__=='__main__':raise SystemExit(main())
