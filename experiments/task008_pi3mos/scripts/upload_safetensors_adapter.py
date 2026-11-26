import base64
import hashlib
import json
from pathlib import Path
from remote_transport import run,ROOT

old='/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1'
new='/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED'
rows=[]
for remote_name,local_name in [
 ('scripts/preprocess.py','scripts/preprocess.py'),('scripts/visualize_masks.py','scripts/visualize_masks.py'),
 ('scripts/infer_pi3mos.py','scripts/infer_pi3mos_safetensors.py'),
 ('scripts/inspect_model_interface.py','scripts/inspect_model_interface.py'),
 ('scripts/summarize_and_visualize.py','scripts/summarize_and_visualize.py'),
 ('configs/night007.json','configs/night007_safetensors.json'),('configs/rgb_only_roi_plan.json','configs/rgb_only_roi_plan.json')]:
    b=(ROOT/local_name).read_bytes();rows.append({'path':remote_name,'content':base64.b64encode(b).decode(),
                                                'sha256':hashlib.sha256(b).hexdigest()})
script='''import base64,hashlib,json,pathlib,shutil
old=pathlib.Path(OLD);new=pathlib.Path(NEW)
failed=json.loads((old/'INFERENCE_STATE.json').read_text())
assert failed['model_forwards_started']==0 and failed['error_type']=='UnpicklingError'
assert json.loads((old/'INFERENCE_EXIT_RECEIPT.json').read_text())['exit_code']==1
new.mkdir(exist_ok=False);(new/'logs').mkdir();(new/'tmp').mkdir()
files=ROWS
for row in files:
 p=new/row['path'];p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(row['content'])
 assert hashlib.sha256(b).hexdigest()==row['sha256']
 with p.open('xb') as f:f.write(b)
for name in ['INPUT_IDENTITY_BEFORE.json','BASELINE_PROTECTION_BEFORE.json','CPU_PREPROCESS_CONTRACT.json',
             'ENV_OFFLINE_STATE.json','ENVIRONMENT_PIP_FREEZE.txt','ENVIRONMENT_PIP_CHECK.txt']:
 shutil.copyfile(old/name,new/name)
receipt={'files':[{'path':r['path'],'sha256':r['sha256']} for r in files],
 'previous_attempt_preserved':str(old),'previous_GPU_forwards':0,'new_algorithm_parameters':False,
 'reason':'Correct verified safetensors binary loader, not a retry of a failed GPU forward'}
(new/'ADAPTER_RELEASE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\\n')
print(json.dumps(receipt,indent=2))
'''.replace('OLD',repr(old)).replace('NEW',repr(new)).replace('ROWS',repr(rows))
print(run(script,'SAFETENSORS_ADAPTER_RELEASE',timeout=60))
launcher=(ROOT/'scripts/remote_launch_inference.py').read_text().replace(old,new)
with (ROOT/'scripts/remote_launch_safetensors.py').open('x',encoding='utf-8') as f:f.write(launcher)
for name in ['remote_inference_status.py','remote_finalize.py','remote_collection_inventory.py']:
 p=ROOT/'scripts'/name;p.write_text(p.read_text().replace(old,new),encoding='utf-8')
