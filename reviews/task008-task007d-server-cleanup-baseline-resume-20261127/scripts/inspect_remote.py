"""Read-only inventory for the user's targeted server cleanup; no model imports."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

def size_tree(path):
    p=Path(path)
    if not p.exists() and not p.is_symlink(): return {"path":str(p),"exists":False}
    st=p.lstat()
    out={"path":str(p),"exists":True,"symlink":p.is_symlink(),"logical_bytes":0,"allocated_bytes":0,"files":0,"directories":0}
    if p.is_symlink():
        out["target"]=os.readlink(p);return out
    if p.is_file():
        out.update(logical_bytes=st.st_size,allocated_bytes=st.st_blocks*512,files=1);return out
    for current,dirs,files in os.walk(p,followlinks=False):
        out["directories"]+=1
        dirs[:]=[d for d in dirs if not Path(current,d).is_symlink()]
        for n in files:
            f=Path(current,n);s=f.lstat()
            if f.is_symlink():continue
            out["files"]+=1;out["logical_bytes"]+=s.st_size;out["allocated_bytes"]+=s.st_blocks*512
    return out

data=Path('/root/rivermind-data')
out={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"hostname":os.uname().nodename,
     "volumes":{p:dict(zip(['total','used','free'],shutil.disk_usage(p))) for p in ['/','/root/rivermind-data','/dev/shm']},
     "data_root_entries":[],"target_inventory":[],"processes":[]}
pattern=re.compile(r'TASK008|TASK007[CD]|OMNIWORLD|OWG|pi3mos',re.I)
for root in [data,Path('/opt'),Path('/root')]:
    for p in sorted(root.iterdir()):
        if root==data:out['data_root_entries'].append({'name':p.name,'directory':p.is_dir(),'symlink':p.is_symlink()})
        if pattern.search(p.name):
            out['target_inventory'].append(size_tree(p))
            if p.is_dir() and not p.is_symlink():
                for c in sorted(p.iterdir()):out['target_inventory'].append(size_tree(c))
external=data/'external_models'
if external.exists():
    for p in sorted(external.iterdir()):
        out['target_inventory'].append(size_tree(p))
        if p.is_dir() and not p.is_symlink():
            for c in sorted(p.iterdir()):
                if c.is_file() or c.name in ['.git','wheels','downloads','cache','weights']:out['target_inventory'].append(size_tree(c))
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        cwd=os.readlink(p/'cwd');exe=os.readlink(p/'exe')
        if pattern.search(args+' '+cwd+' '+exe):
            out['processes'].append({'pid':int(p.name),'executable':exe,'cwd':cwd,'matched_labels':sorted(set(pattern.findall(args+' '+cwd+' '+exe)))})
    except (OSError,PermissionError):pass
for name,args in [('gpu',['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader']),
                  ('gpu_processes',['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader']),
                  ('data_mount',['findmnt','-T',str(data),'-J'])]:
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=30)
        out[name]={'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
    except OSError as e:
        out[name]={'returncode':None,'stdout':'','stderr':str(e)}
print(json.dumps(out,ensure_ascii=False,indent=2))
