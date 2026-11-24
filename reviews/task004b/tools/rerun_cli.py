from transport import *
import json
x=rpc(r'''import sys,json,subprocess,pathlib
s=json.loads(sys.stdin.readline());p=subprocess.run([s['bin'],'--help'],capture_output=True,text=True,timeout=20);print(json.dumps(dict(exit_code=p.returncode,help=p.stdout,stderr=p.stderr)))''',{'bin':"/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/lib/python3.10/site-packages/rerun_sdk/rerun_cli/rerun"},'RERUN_NATIVE_CLI_AUDIT')
print(x['help'])
