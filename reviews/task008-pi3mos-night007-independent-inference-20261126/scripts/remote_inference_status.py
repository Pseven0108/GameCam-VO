import json
from pathlib import Path
import shutil
import subprocess
w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
for name in ['INFERENCE_STATE.json','INFERENCE_EXIT_RECEIPT.json']:
    p=w/name
    if p.exists():print(name,p.read_text())
p=w/'logs/INFERENCE.log'
if p.exists():print('LOG_TAIL',p.read_text(errors='replace')[-3000:])
print('GPU',subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader'],text=True).strip())
print('free_disk',json.dumps({p:shutil.disk_usage(p).free for p in ['/','/root/rivermind-data']}))
