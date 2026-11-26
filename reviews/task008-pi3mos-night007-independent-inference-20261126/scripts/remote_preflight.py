"""Read-only resource and repository authorization probe, no framework imports."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def call(args,timeout=20):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return {'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace').strip(),
            'stderr':p.stderr.decode('utf-8',errors='replace').strip()}


data={'hostname':os.uname().nodename,'GPU':call(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.total,memory.free','--format=csv,noheader']),
      'GPU_processes':call(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader']),
      'volumes':{},'conda_candidates':{},'project_directories':[],'framework_imported':False,'GPU_model_runs':0}
for path in ['/','/opt','/root/rivermind-data','/dev/shm']:
    q=Path(path);s=shutil.disk_usage(q);data['volumes'][path]={'total':s.total,'used':s.used,'free':s.free}
for name in ['/root/miniconda3/bin/conda','/opt/conda/bin/conda','/opt/miniconda3/bin/conda','/root/miniforge3/bin/conda']:
    if Path(name).is_file():data['conda_candidates'][name]=True
for q in ['/root/rivermind-data','/opt','/root']:
    data['project_directories'].append({'root':q,'names':[x.name for x in Path(q).iterdir() if x.is_dir() and not x.name.startswith('.')][:110]})
wrapper=Path('/usr/local/bin/gamecam-gh')
data['GitHub']={'credential_wrapper_present':wrapper.is_file() and os.access(wrapper,os.X_OK)}
if data['GitHub']['credential_wrapper_present']:
    p=subprocess.run([str(wrapper),'api','repos/Pseven0108/GameCam-VO'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
    data['GitHub']['repository_read_exit_code']=p.returncode
    if p.returncode==0:
        d=json.loads(p.stdout);data['GitHub'].update(repository=d['full_name'],visibility=d['visibility'],permissions=d.get('permissions',{}),default_branch=d['default_branch'])
    else:data['GitHub']['status']='AUTH_OR_NETWORK_NOT_CONFIRMED; arbitrary CLI diagnostics withheld'
print(json.dumps(data,indent=2))
