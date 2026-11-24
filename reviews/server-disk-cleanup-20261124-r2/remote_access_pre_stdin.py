import base64,hashlib,importlib.util,json,os,pathlib,shlex,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parent
BOOT=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z\bootstrap')
spec=importlib.util.spec_from_file_location('cleanup_pinned_ssh',BOOT/'run_once.py')
ssh=importlib.util.module_from_spec(spec);spec.loader.exec_module(ssh)
pre=json.loads((BOOT/'evidence/preflight.json').read_text())
def call(label,code,timeout=240):
    base=ssh.ssh_base(pre);base[base.index('-p')+1]='REDACTED_SSH_PORT'
    loader='import base64;exec(compile(base64.b64decode('+repr(base64.b64encode(code.encode()).decode())+'),"<disk-cleanup>","exec"))'
    cmd='exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -c '+shlex.quote(loader)
    start=time.time()
    out=ROOT/(label+'.stdout.json');err=ROOT/(label+'.stderr.txt')
    with out.open('xb') as of,err.open('xb') as ef:
        p=subprocess.run(base+['-o','ClearAllForwardings=yes',ssh.HOST,cmd],stdout=of,stderr=ef,timeout=timeout,creationflags=ssh.CREATE)
    receipt={'label':label,'endpoint':'RENTAL_SSH_HOST:REDACTED_SSH_PORT','start_unix':start,'end_unix':time.time(),'exit_code':p.returncode,'trust':ssh.verified(err),'code_sha256':hashlib.sha256(code.encode()).hexdigest()}
    (ROOT/(label+'.receipt.json')).write_text(json.dumps(receipt,indent=2))
    if p.returncode or not all(receipt['trust'].values()):raise RuntimeError(receipt)
    return json.loads(out.read_text())
if __name__=='__main__':
    label=sys.argv[1]
    result=call(label,(ROOT/(label+'.py')).read_text(encoding='utf-8-sig'),timeout=300)
    print(json.dumps(result,ensure_ascii=False,indent=2))
