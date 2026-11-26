import json
import subprocess
commands=[['git','--version'],['/usr/local/bin/gamecam-gh','auth','git-credential','--help']]
rows=[]
for args in commands:
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    rows.append({'capability':'git' if args[0]=='git' else 'gh_auth_git_credential_helper',
                 'exit_code':r.returncode,'available':r.returncode==0})
print(json.dumps(rows,indent=2))
