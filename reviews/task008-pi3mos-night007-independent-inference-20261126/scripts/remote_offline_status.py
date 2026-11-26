import json
from pathlib import Path
import shutil
w=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
s=w/'ENV_OFFLINE_STATE.json'
print(s.read_text() if s.exists() else 'OFFLINE_INSTALL_NOT_STARTED')
for name in ['INSTALL_OFFLINE.log','ENV_OFFLINE_CONTROLLER.log']:
    p=w/'logs'/name
    if p.exists():print(name,p.read_text(errors='replace')[-3000:])
print('free_disk',json.dumps({p:shutil.disk_usage(p).free for p in ['/','/root/rivermind-data']}))
files=list((w/'wheelhouse').glob('*.whl'))
print('wheelhouse',json.dumps({'files':len(files),'bytes':sum(p.stat().st_size for p in files),
                              'newest':[p.name for p in sorted(files,key=lambda p:p.stat().st_mtime)[-3:]]}))
