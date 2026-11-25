"""Read-only R2 intake; deliberately does not import torch or expose process args."""
import pathlib, json, hashlib, subprocess, shutil, os
OLD=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')
HIST=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
ENV=pathlib.Path('/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def command(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=30)
 return dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
snap=OLD/'snapshots/D0_S1_RGB233'
files={}
for p in list(snap.iterdir())+list((OLD/'build_attempt02').glob('*.so'))+list(ENV.glob('lib/python*/site-packages/droid_backends*.so')):
 if p.is_file():files[str(p)]={'bytes':p.stat().st_size,'sha256':sha(p)}
out={'gpu':command(['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader']),
 'gpu_processes':command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),
 'disk':dict(zip(('total','used','free'),shutil.disk_usage('/root/rivermind-data'))),
 'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'files':files,
 'historical_head':command(['git','-C',str(HIST/'source_candidate'),'rev-parse','HEAD']),
 'historical_status':command(['git','-C',str(HIST/'source_candidate'),'status','--porcelain']),
 'new_root_exists':pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1').exists()}
print(json.dumps(out,indent=2))
