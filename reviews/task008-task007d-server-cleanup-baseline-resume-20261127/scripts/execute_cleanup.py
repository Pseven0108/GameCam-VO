"""Execute the reviewed exact cleanup plan using the trusted SSH transport."""
import json
from pathlib import Path
from transport import ROOT,mod

plan=json.loads((ROOT/'CLEANUP_AUTHORIZATION_PLAN.json').read_text('utf-8'))
script='PLAN='+repr(plan)+'\n'+(ROOT/'cleanup_remote.py').read_text('utf-8')
result=mod.run(script,'CLEANUP_EXECUTION',timeout=300)
(ROOT/'CLEANUP_FINAL_RECEIPT.json').write_text(result,encoding='utf-8')
print(result)
