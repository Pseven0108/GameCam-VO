import json,sys
from remote_cpu import call,ROOT
code=r'''
import json,pathlib,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
results={}
for name in ('FORMAT_UNIT_R1','REAL_MODEL_FORMAT_ROUNDTRIP_R1'):
 p=r/'cpu_tests'/name
 results[name]={'files':[x.name for x in p.iterdir()] if p.exists() else []}
 for f in ('PROCESS_RECEIPT.json','FORMAT_UNIT_TEST_REPORT.json','FRESH_PROCESS_EXIT.json','FRESH_PROCESS_RECEIPT.json','process.stdout.txt','process.stderr.txt','restore_child.stderr.txt'):
  q=p/f
  if q.is_file():results[name][f]=q.read_text()[-3600:]
print(json.dumps(results))
'''
out=call(sys.argv[1],code,timeout=120)
(ROOT/'evidence'/(sys.argv[1]+'.json')).write_text(out)
print(out)
