import sys,pathlib,importlib.util,json,subprocess,time,argparse,shlex
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
BOOT=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z\bootstrap')
spec=importlib.util.spec_from_file_location('historical_ssh_pin',BOOT/'run_once.py')
ssh=importlib.util.module_from_spec(spec);spec.loader.exec_module(ssh)
pre=json.loads((BOOT/'evidence/preflight.json').read_text())
def base():
 b=ssh.ssh_base(pre);b[b.index('-p')+1]='30601';return b
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('script');p.add_argument('label');p.add_argument('--python',default='/usr/bin/python3');p.add_argument('--timeout',type=int,default=90);p.add_argument('--gpu',action='store_true');a=p.parse_args()
 script=pathlib.Path(a.script).read_bytes();out=ROOT/'00_intake';start=time.time()
 cmd='exec env PYTHONDONTWRITEBYTECODE=1 '+('' if a.gpu else 'CUDA_VISIBLE_DEVICES= ')+shlex.quote(a.python)+' -B -u -'
 with (out/(a.label+'.stdout.txt')).open('xb') as of,(out/(a.label+'.stderr.txt')).open('xb') as ef:
  r=subprocess.run(base()+['-o','ClearAllForwardings=yes',ssh.HOST,cmd],input=script,stdout=of,stderr=ef,timeout=a.timeout,creationflags=ssh.CREATE)
 receipt={'exit_code':r.returncode,'started_unix':start,'finished_unix':time.time(),'trust':ssh.verified(out/(a.label+'.stderr.txt')),'endpoint':'sc01-ssh.gpuhome.cc:30601','gpu_visibility_enabled':a.gpu}
 (out/(a.label+'.receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt));assert r.returncode==0 and all(receipt['trust'].values())
