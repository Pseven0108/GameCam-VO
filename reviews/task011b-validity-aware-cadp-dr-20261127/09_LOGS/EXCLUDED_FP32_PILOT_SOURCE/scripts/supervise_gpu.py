"""One GPU job at a time; archive/verify before recycling only new task files."""
import csv,hashlib,json,os,shlex,subprocess,tarfile,time
from pathlib import Path
from common import TASK,dump,sha
from remote_transport import SSH,options

REMOTE='/root/rivermind-data/GAMECAM_TASK011B_20261127_R1'
PY='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
LOCAL=TASK/'gpu_results'


def ssh(command,**kw):
    return subprocess.run([str(SSH),'-T','-p','31454',*options(),'root@sc01-ssh.gpuhome.cc',command],capture_output=True,timeout=kw.pop('timeout',7200),**kw)


def query(code):
    p=ssh('/usr/bin/python3 -c '+shlex.quote(code))
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-1400:])
    return json.loads(p.stdout)


def service(kind,window,arm=None):
    label=kind+'_'+window+('_'+arm if arm else '')
    path=REMOTE+'/job_receipts/'+label+'.json'
    old=query(f'import json\nfrom pathlib import Path\np=Path({path!r})\nprint(p.read_text() if p.exists() else "null")')
    if old and old['status'] in ('RUNNING','STARTED'):
        while old['status'] in ('RUNNING','STARTED'):
            time.sleep(15)
            old=query(f'from pathlib import Path\nprint(Path({path!r}).read_text())')
    if old:
        if old['status'] not in ('COMPLETE','ALGORITHM_FAILURE'):raise RuntimeError('Existing failed job; no retry: '+label)
        return old
    cmd=shlex.join([PY,'-u','-B',REMOTE+'/gpu/job_service.py',kind,window]+(['--arm',arm] if arm else []))
    print('GPU_START',label,flush=True)
    p=ssh(cmd)
    (LOCAL/'service_logs').mkdir(parents=True,exist_ok=True)
    (LOCAL/'service_logs'/(label+'.stdout')).write_bytes(p.stdout)
    (LOCAL/'service_logs'/(label+'.stderr')).write_bytes(p.stderr)
    if p.returncode:raise RuntimeError('GPU job failed; no automatic retry: '+label+' '+p.stdout.decode(errors='replace')[-600:])
    result=json.loads(p.stdout.decode().strip().splitlines()[-1])
    print('GPU_END',label,result['status'],round(result['seconds'],2),flush=True)
    return result


def collect(kind,window,arm=None,cleanup=True):
    label=kind+'_'+window+('_'+arm if arm else '')
    dest=LOCAL/'archives'/(label+'.tar.gz');dest.parent.mkdir(parents=True,exist_ok=True)
    proof=LOCAL/'receipts'/(label+'.json')
    if proof.exists():return json.loads(proof.read_text())
    cmd=shlex.join([PY,'-B',REMOTE+'/gpu/archive_outputs.py',kind,window]+(['--arm',arm] if arm else []))
    p=ssh(cmd)
    if p.returncode:raise RuntimeError('Archive failed: '+p.stderr.decode(errors='replace')[-1000:])
    remote=json.loads(p.stdout.decode().strip().splitlines()[-1])
    with dest.open('xb') as stream:
        proc=subprocess.Popen([str(SSH),'-T','-p','31454',*options(),'root@sc01-ssh.gpuhome.cc','/usr/bin/python3 -c '+shlex.quote('import sys\nfrom pathlib import Path\nwith Path('+repr(remote['archive'])+').open("rb") as f:\n import shutil;shutil.copyfileobj(f,sys.stdout.buffer)')],stdout=stream,stderr=subprocess.PIPE)
        _,error=proc.communicate(timeout=600)
    if proc.returncode or sha(dest)!=remote['sha256']:raise RuntimeError('Archive transfer hash failed')
    extracted=LOCAL/'raw'/label;extracted.mkdir(parents=True,exist_ok=False)
    with tarfile.open(dest,'r:gz') as t:
        for m in t.getmembers():
            target=(extracted/m.name).resolve()
            if not target.is_relative_to(extracted.resolve()) or m.issym() or m.islnk():raise RuntimeError('Unsafe result archive')
            if m.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                assert m.isfile();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(t.extractfile(m).read())
    files=json.loads((extracted/'result/OUTPUT_SHA256.json').read_text())['files']
    for item in files:
        if sha(extracted/'result'/item['path'])!=item['sha256']:raise RuntimeError('Internal output SHA mismatch')
    receipt=dict(**remote,local_archive=str(dest),local_extracted=str(extracted/'result'),verified_files=len(files),all_internal_SHA256=True,remote_cleaned=False)
    dump(proof,receipt)
    if cleanup:clean(receipt);receipt['remote_cleaned']=True;dump(proof,receipt)
    return receipt


def clean(receipt):
    code=f'''import json,shutil,hashlib\nfrom pathlib import Path\nr=Path({REMOTE!r}).resolve()\ns=Path({receipt['source']!r});a=Path({receipt['archive']!r})\nassert s.resolve().is_relative_to(r) and a.resolve().is_relative_to(r/"transfers")\nassert s.parts[len(r.parts)] in ("runs","cache") and not s.is_symlink()\nassert hashlib.sha256(a.read_bytes()).hexdigest()=={receipt['sha256']!r}\n# Job service waited for all owning GPU processes before archive creation.\n# Recheck no live process maps a path under this new task output.\nfor process in Path("/proc").iterdir():\n if not process.name.isdigit():continue\n for fd in (process/"fd").glob("*"):\n  try:link=str(fd.readlink())\n  except OSError:continue\n  assert not link.startswith(str(s)+"/"),"Output remains open"\nshutil.rmtree(s);a.unlink()\nprint(json.dumps(dict(deleted_only_new_task_output=str(s),local_SHA_verified_before_cleanup=True)))'''
    value=query(code)
    dump(LOCAL/'cleanup'/(receipt['label']+'.json'),value)


def main():
    LOCAL.mkdir(parents=True,exist_ok=True)
    windows=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']
    schedule=[dict(window=x['window_id'],arm='A'+str((j+i)%7)) for i,x in enumerate(windows) for j in range(7)]
    sched=TASK/'configs/GPU_RUN_ORDER_FROZEN.json'
    if sched.exists():assert json.loads(sched.read_text())==schedule
    else:dump(sched,schedule)
    count=0
    for window in windows:
        wid=window['window_id']
        service('cache',wid);cache=collect('cache',wid,cleanup=False)
        for step in [r for r in schedule if r['window']==wid]:
            arm=step['arm'];receiptfile=LOCAL/'receipts'/('window_'+wid+'_'+arm+'.json')
            if not receiptfile.exists():
                receipt=service('window',wid,arm);collect('window',wid,arm)
            count+=1;dump(LOCAL/'PROGRESS.json',dict(terminal=count,planned=140,current_window=wid,current_arm=arm))
            print('TERMINAL',count,'/140',wid,arm,flush=True)
        if not cache.get('remote_cleaned'):
            clean(cache);cache['remote_cleaned']=True;dump(LOCAL/'receipts'/('cache_'+wid+'.json'),cache)
    dump(LOCAL/'BATCH_COMPLETE.json',dict(status='ALL_140_TERMINAL',terminal=140,windows=20,new_datasets_downloaded=False))
    print('ALL_GPU_WINDOWS_TERMINAL',flush=True)


if __name__=='__main__':main()
