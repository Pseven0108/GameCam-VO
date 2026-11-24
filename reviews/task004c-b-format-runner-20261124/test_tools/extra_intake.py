import base64,json,pathlib
from remote_cpu import call,ROOT
code=r'''
import base64,json,pathlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
s=r/'source_candidate'
names=['native_control/admission.py','native_control/install.py','native_control/binding.py','native_control/file_backed.py','native_control/closure.py','src/utils/datasets.py','src/utils/eval_traj.py','src/trajectory_filler.py','task004_controls.py','native_control/launch.py','native_control/policy.py']
out={'source':{},'metadata':{}}
for n in names:
 if (s/n).is_file():out['source'][n]=base64.b64encode((s/n).read_bytes()).decode()
for name in ('configs/identity_lock.json','evidence/APPROVED_47_FAMILY_PROTOCOL.json','evidence/FILE_BACKED_CPU_VALIDATION.json','cpu_tests/REAL_MODEL_FORMAT_ROUNDTRIP_R1/FRESH_PROCESS_RECEIPT.json','cpu_tests/REAL_MODEL_FORMAT_ROUNDTRIP_R1/SNAPSHOT_REUSE.json','cpu_tests/REAL_MODEL_FORMAT_ROUNDTRIP_R1/FORMAT_ROUNDTRIP_REPORT.json'):
 if (r/name).is_file():out['metadata'][name]=base64.b64encode((r/name).read_bytes()).decode()
print(json.dumps(out))
'''
a=json.loads(call('FORMAT_EXTRA_STATIC_INTAKE',code,timeout=120))
for group,dest in [('source','source_intake'),('metadata','remote_evidence')]:
 for n,b in a[group].items():
  p=ROOT/dest/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(b,validate=True))
print(json.dumps({k:list(v) for k,v in a.items()}))
