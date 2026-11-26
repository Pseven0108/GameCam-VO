"""Pinned SSH for CPU restoration only. No permanent SSH changes."""
import argparse,json,os,pathlib,subprocess,time
from common import *
SSH=pathlib.Path(os.environ['WINDIR'])/'System32/OpenSSH/ssh.exe'
KEY=pathlib.Path.home()/'.ssh/id_ed25519_rivermind_codex'
KNOWN=PROJECT/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/evidence/sc01-30723.known_hosts'
PIN='SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA'
REMOTE='/root/rivermind-data/GAMECAM_TASK006A_R2_2_CPU_RESTORE_20261126_R1'
PY='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
def opts():
    keyinfo=subprocess.check_output([str(SSH.with_name('ssh-keygen.exe')),'-lf',str(KNOWN),'-E','sha256'],text=True)
    if PIN not in keyinfo: raise RuntimeError('Established host key identity unavailable')
    o={'BatchMode':'yes','IdentitiesOnly':'yes','StrictHostKeyChecking':'yes','UserKnownHostsFile':str(KNOWN),
       'GlobalKnownHostsFile':'none','HostKeyAlias':'[sc01-ssh.gpuhome.cc]:30723','HostKeyAlgorithms':'ssh-ed25519',
       'UpdateHostKeys':'no','ForwardAgent':'no','ForwardX11':'no','ConnectionAttempts':'1','ConnectTimeout':'10'}
    return ['-F','none','-i',str(KEY)]+[i for k,v in o.items() for i in ['-o',k+'='+v]]
def run(script,label,python=PY,timeout=240):
    cpu_only();base=ROOT/'logs';t=time.perf_counter()
    cmd=[str(SSH),'-v','-T','-p','31136',*opts(),'root@sc01-ssh.gpuhome.cc',
         'exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 '+python+' -B -u -']
    with (base/(label+'.stdout.txt')).open('xb') as out,(base/(label+'.stderr.txt')).open('xb') as err:
        p=subprocess.run(cmd,input=script.encode(),stdout=out,stderr=err,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    s=(base/(label+'.stderr.txt')).read_text('utf-8',errors='replace')
    receipt={'exit_code':p.returncode,'host_key_verified':('Server host key: ssh-ed25519 '+PIN in s and 'is known and matches the ED25519 host key' in s),
       'elapsed_seconds':time.perf_counter()-t,'CPU_only':True,'model_forward':False,'endpoint':'sc01-ssh.gpuhome.cc:31136'}
    dump(base/(label+'.receipt.json'),receipt)
    if p.returncode or not receipt['host_key_verified']: raise RuntimeError('Trusted CPU command failed; see saved logs')
    return (base/(label+'.stdout.txt')).read_text('utf-8')
def download():
    local=ROOT/'02_restoration/torch_CPU';local.mkdir(exist_ok=False)
    listing=json.loads(run("import json,pathlib,hashlib\np=pathlib.Path('"+REMOTE+"')\nprint(json.dumps([{'name':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(p.iterdir()) if f.is_file()]))",'CPU_DOWNLOAD_INDEX',python='/usr/bin/python3'))
    audits=[]
    for row in listing:
        name=row['name']
        if pathlib.PurePosixPath(name).name!=name or row['bytes']>150_000_000: raise RuntimeError('Invalid transfer path/size')
        dest=local/name
        args=[str(SSH),'-T','-p','31136',*opts(),'root@sc01-ssh.gpuhome.cc','exec /bin/cat -- '+REMOTE+'/'+name]
        with dest.open('xb') as f:
            p=subprocess.run(args,stdout=f,stderr=subprocess.PIPE,timeout=100,creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode or dest.stat().st_size!=row['bytes'] or sha(dest)!=row['sha256']:raise RuntimeError('Transfer identity mismatch')
        audits.append({**row,'verified':True})
    dump(local/'DOWNLOAD_VERIFICATION.json',{'files':audits,'all_verified':True})
    print(json.dumps({'files':len(audits),'bytes':sum(r['bytes'] for r in audits)}))
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['run','download']);a=p.parse_args()
    if a.mode=='run':
        script=(ROOT/'code/remote_cpu_restore.py').read_text('utf-8')
        # Save an independent script file and execute it; preserve stdin receipts.
        remote_script=REMOTE+'_runner.py'
        launcher="import pathlib,runpy\np=pathlib.Path("+repr(remote_script)+")\nwith p.open('x',encoding='utf-8') as f:f.write("+repr(script)+")\nrunpy.run_path(str(p),run_name='__main__')\n"
        print(run(launcher,'CPU_RESTORE'))
    else:download()
if __name__=='__main__':main()
