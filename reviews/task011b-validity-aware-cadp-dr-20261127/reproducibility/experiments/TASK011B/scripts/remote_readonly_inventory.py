"""Additional resource evidence: distinguish a broken utility from no devices."""
import json
from remote_transport import run
from common import TASK,dump

SCRIPT=r'''
import json,glob,os,subprocess
from pathlib import Path
def children(path):
 p=Path(path);return [str(x) for x in p.iterdir()] if p.is_dir() else []
def call(a):
 try:
  p=subprocess.run(a,capture_output=True,text=True,timeout=10)
  return dict(code=p.returncode,stdout=p.stdout[-3000:],stderr=p.stderr[-1200:])
 except Exception as e:return dict(error=str(e))
out=dict(hostname=os.uname().nodename,nvidia_device_nodes=glob.glob('/dev/nvidia*'),
 nvidia_proc_version=Path('/proc/driver/nvidia/version').read_text() if Path('/proc/driver/nvidia/version').is_file() else None,
 conda_environments={p:children(p) for p in ['/root/miniconda3/envs','/opt/conda/envs','/root/.conda/envs']},
 resources=call(['df','-B1','/','/dev/shm','/root/rivermind-data']),
 current_research_status=json.loads(Path('/root/rivermind-data/GAMECAM_RESEARCH_DIRECTION_CURRENT.json').read_text()) if Path('/root/rivermind-data/GAMECAM_RESEARCH_DIRECTION_CURRENT.json').is_file() else None,
 baseline_dirs={p:children(p)[:25] for p in ['/root/rivermind-data/DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1',
 '/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408']})
print(json.dumps(out,indent=2))
'''

if __name__=='__main__':
    result=json.loads(run(SCRIPT,'READONLY_INVENTORY_001'))
    dump(TASK/'intake/REMOTE_RESOURCE_STATUS.json',result)
    print(json.dumps(result,indent=2))
