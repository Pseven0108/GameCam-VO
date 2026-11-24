import json,sys
from transport import ROOT,rpc
spec=json.loads((ROOT/'release/AUTHORIZATION.json').read_text())
bootstrap=json.loads((ROOT/'bootstrap/evidence/BOOTSTRAP_PASS.json').read_text())
arm=sys.argv[1]
rpc((ROOT/'tools/remote_execute_one.py').read_text(),'RUN_'+arm,3800,dict(root=spec['remote_root'],arm=arm,viewer=bootstrap['viewer']))
