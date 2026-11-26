"""Locate existing RGB, preserve repository states, inspect available base setup."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path('/root/rivermind-data')
def call(args,timeout=30):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return {'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace').strip(),
            'stderr':p.stderr.decode('utf-8',errors='replace').strip()}

data={'conda_envs':call(['/opt/conda/bin/conda','env','list','--json']),
      'conda_pkg_cache_bytes':0,'night_manifests':[],'RGB_candidates':[],'git_repositories':[]}
for d in ['DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1','VIPER_MATCHED_DUAL_BASELINE_R2','DROID_W_TASK003_VAL007_OBSERVATION_R1']:
    p=ROOT/d
    for relative in ['manifests/val_007_full_00001-00487.json','inputs/manifests/val_007_full_00001-00487.json','data/rgb/val_007_full_00001-00487','data/val_007_full_00001-00487','data/rgb/val_007','rgb/val_007_full_00001-00487','inputs/rgb']:
        q=p/relative
        if q.is_file() and q.suffix=='.json':data['night_manifests'].append({'path':str(q),'bytes':q.stat().st_size,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()})
        elif q.is_dir():data['RGB_candidates'].append({'path':str(q),'sample_names':[x.name for x in list(q.iterdir())[:8]]})
    if p.is_dir():data.setdefault('experiment_root_dirs',[]).append({'path':str(p),'dirs':[x.name for x in p.iterdir() if x.is_dir()]})
codebase=Path('/opt/gamecam-viper-fullseq-3090-20261120-061408')
if codebase.is_dir():
    data['system_code_root']=[x.name for x in codebase.iterdir()]
    for current,dirs,files in os.walk(codebase):
        relative=Path(current).relative_to(codebase)
        dirs[:]=[d for d in dirs if d not in ['envs','pkgs','.cache','site-packages','checkpoints']]
        if len(relative.parts)>3:dirs[:]=[];continue
        if '.git' in dirs:
            p=Path(current);data['git_repositories'].append({'path':str(p),'HEAD':call(['git','-C',str(p),'rev-parse','HEAD']),
                'status':call(['git','-C',str(p),'status','--porcelain','-uno'])});dirs.remove('.git')
data['system_python_env_existing']=Path('/opt/gamecam-pi3mos/envs/pi3mos-infer').exists()
print(json.dumps(data,indent=2))
