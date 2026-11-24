import sys,json
from remote_cpu import ROOT,call
code=r'''
import json,pathlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
paths=['cpu_tests/DRIVER_INTEGRATION_CPU_R1/process.stderr.txt','cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/PROCESS_RECEIPT.json','cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/FRESH_PROCESS_RECEIPT.json']
print(json.dumps({p:(r/p).read_text() if (r/p).is_file() else None for p in paths}))
'''
out=call('DRIVER_CPU_FAILURE_AND_FINAL_RESTORE_READBACK',code,timeout=120)
(ROOT/'evidence/DRIVER_CPU_FAILURE_AND_FINAL_RESTORE_READBACK.json').write_text(out);print(out)
