"""Explicit CPU-only read script runner. Each receipt is new and immutable."""
import argparse,json,pathlib,subprocess,time
from remote_probe import ssh_base,PIN,ROOT

def main():
 p=argparse.ArgumentParser();p.add_argument('script');p.add_argument('label');p.add_argument('--timeout',type=int,default=60);p.add_argument('--summary',action='store_true');a=p.parse_args()
 dest=ROOT/'00_project_audit'; stem=a.label
 args=ssh_base()+['root@sc01-ssh.gpuhome.cc','exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -']
 started=time.time()
 with (dest/(stem+'.stdout.txt')).open('xb') as out,(dest/(stem+'.stderr.txt')).open('xb') as err:
  c=subprocess.run(args,input=pathlib.Path(a.script).read_bytes(),stdout=out,stderr=err,timeout=a.timeout,creationflags=subprocess.CREATE_NO_WINDOW)
 log=(dest/(stem+'.stderr.txt')).read_text(encoding='utf-8',errors='replace')
 receipt={'exit_code':c.returncode,'elapsed_seconds':time.time()-started,'CPU_only':True,
 'server_host_key_matches_pin':'Server host key: ssh-ed25519 '+PIN in log and 'is known and matches the ED25519 host key' in log,
 'authenticated':'using "publickey"' in log}
 (dest/(stem+'.receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(receipt))
 if c.returncode: raise SystemExit(c.returncode)
 if not receipt['server_host_key_matches_pin'] or not receipt['authenticated']: raise RuntimeError('Unverified SSH identity')
 if not a.summary: print((dest/(stem+'.stdout.txt')).read_text(encoding='utf-8'))

if __name__=='__main__':main()
