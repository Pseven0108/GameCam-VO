"""Current-task completion watcher and CPU analyses; no new GPU or later stage."""
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
deadline=time.monotonic()+3*3600;path=TASK/'private/forkserver_holdout_STATE.json'
while time.monotonic()<deadline:
    if path.exists():
        state=json.loads(path.read_text())
        if state['status']=='COMPLETE':break
        if state['status']!='STARTED':raise RuntimeError('Frozen experiment stopped; no follow-up run or automatic retry')
    time.sleep(3)
else:raise RuntimeError('Bounded completion watch expired')
for script in ['evaluate_runs.py','summarize_experiments.py','compile_evidence_tables.py',
    'camera_residual_diagnostic.py','native_u_model_overlap.py','phase_filler_diagnostic.py',
    'render_result_figures.py','verify_asset_protection.py','synthesize_final_report.py']:
    print('CPU_ANALYSIS',script,flush=True)
    subprocess.run([sys.executable,'-u','-B','experiments/TASK010-A/scripts/'+script],cwd=ROOT,check=True)
versions={}
for name in ['torch','torchvision','numpy','scipy','opencv-python','Pillow','scikit-learn','timm','safetensors','transformers','einops','matplotlib','requests','huggingface-hub']:
    try:versions[name]=metadata.version(name)
    except metadata.PackageNotFoundError:versions[name]='NOT_INSTALLED'
gpu=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],capture_output=True,text=True)
(TASK/'09_reproducibility/ENVIRONMENT_WINDOWS.json').write_text(json.dumps({'python':sys.version,
    'executable':sys.executable,'packages':versions,'actual_GPU_driver':gpu.stdout.strip(),
    'native_runtime':'Preserved TASK009 WSL Python3.10 / torch2.7.1+cu128; original extension hashes in every receipt',
    'production_environment_install_changes_this_task':False},indent=2))
(TASK/'private/ANALYSIS_COMPLETE.json').write_text(json.dumps({'status':'COMPLETE','new_GPU_work_started':False},indent=2))
print('FIXED_EXPERIMENT_AND_CPU_ANALYSIS_COMPLETE_NO_NEXT_STAGE',flush=True)
