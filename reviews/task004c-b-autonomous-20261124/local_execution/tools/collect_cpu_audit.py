import json
from remote_cpu import ROOT,call
code=r'''
import json,pathlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
p=r/'cpu_tests/closure_audit_round0_models/CPU_REAL_MODEL_OBJECT_AUDIT.json'
print(p.read_text())
'''
d=json.loads(call('COLLECT_CPU_AUDIT_R0',code))
(ROOT/'evidence/CPU_REAL_MODEL_OBJECT_AUDIT_R0.json').write_text(json.dumps(d,indent=2))
print(json.dumps({'models':d['models'],'function_count':len(d['functions']),'function_example':d['functions'][:1],'unsupported':d['unsupported'],'cuda_initialized':d['cuda_initialized']},indent=2))
