import json
from pathlib import Path
import shutil
p=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')
state=p/('ENV_RECOVERY_STATE.json' if (p/'ENV_RECOVERY_STATE.json').exists() else 'ENV_SETUP_STATE.json' if (p/'ENV_SETUP_STATE.json').exists() else 'SETUP_STATE.json')
s=json.loads(state.read_text()) if state.exists() else {'stage':'NO_STATE_YET'}
print(json.dumps(s,indent=2))
for log in sorted((p/'logs').glob('*.log')):
    if log.name==s.get('stage','')+'.log' or (s.get('stage') in ['SETUP_STOPPED','ENV_SETUP_STOPPED','ENV_RECOVERY_STOPPED'] and log.name in ['ENV_RECOVERY_CONTROLLER.log','ENV_SETUP_CONTROLLER.log','INSTALL_EXACT_OFFICIAL_WHEELS.log','INSTALL_MINIMAL_MODEL_DEPS_RECOVERY.log']):
        print('LOG',log.name)
        print(log.read_text(errors='replace')[-3500:])
print('FREE',json.dumps({x:shutil.disk_usage(x).free for x in ['/','/root/rivermind-data']}))
files=sorted([q for q in (p/'tmp').rglob('*') if q.is_file()],key=lambda q:q.stat().st_size,reverse=True)[:4]
print('TEMP_DOWNLOAD_BYTES',json.dumps([{'name':q.name,'bytes':q.stat().st_size} for q in files]))
