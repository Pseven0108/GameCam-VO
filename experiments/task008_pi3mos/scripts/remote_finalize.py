"""CPU summaries and byte-identity protection after the approved serial inference."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
state=json.loads((w/'INFERENCE_STATE.json').read_text())
assert state['stage']=='COMPLETE_A_B_INFERENCE' and state['model_forwards_complete']==64
assert json.loads((w/'INFERENCE_EXIT_RECEIPT.json').read_text())['exit_code']==0
py='/opt/gamecam-pi3mos/envs/pi3mos-infer/bin/python'
args=[py,'-B','-u',str(w/'scripts/summarize_and_visualize.py'),'--config',str(w/'configs/night007.json'),
      '--roi-plan',str(w/'configs/rgb_only_roi_plan.json')]
with (w/'logs/CPU_SUMMARY.log').open('xb') as f:
    r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=180,
                     env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
assert r.returncode==0,'CPU summary failed; preserve existing inference outputs'
counts={}
for name,key in [('INPUT_IDENTITY_BEFORE.json','frames'),('BASELINE_PROTECTION_BEFORE.json','files')]:
    rows=json.loads((w/name).read_text())[key]
    for row in rows:
        p=Path(row['path']);assert p.stat().st_size==row['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'Protected original asset changed'
    counts[name]=len(rows)
protection={'SHA256_identity':'PASS','counts':counts,'DROID_W_modified':False,'Metric3D_or_BA_run':False,
            'Pi3MOS_source_worktree':subprocess.check_output(['git','-C',json.loads((w/'configs/night007.json').read_text())['model_source_outside_project'],'status','--porcelain'],text=True)}
assert protection['Pi3MOS_source_worktree']==''
with (w/'ORIGINAL_ASSET_PRESERVATION.json').open('x') as f:json.dump(protection,f,indent=2);f.write('\n')
resource={'volumes':{p:dict(zip(['total','used','free'],shutil.disk_usage(p))) for p in ['/','/root/rivermind-data','/dev/shm']},
          'GPU':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader'],text=True).strip(),
          'compute_processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True).strip(),
          'instance_shutdown_or_reboot':False}
with (w/'FINAL_RESOURCE_STATUS.json').open('x') as f:json.dump(resource,f,indent=2);f.write('\n')
print(json.dumps({'status':'COMPLETE_A_B_AND_CPU_SUMMARIES','protected_assets':protection,
                  'statistics':json.loads((w/'TASK008_SUMMARY_STATISTICS.json').read_text()),'resources':resource},indent=2))
