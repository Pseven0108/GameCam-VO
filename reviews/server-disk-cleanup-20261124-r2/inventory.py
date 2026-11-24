import collections,json,os,pathlib,shutil,socket,stat,subprocess,time
base=pathlib.Path('/root/rivermind-data');assert base.is_dir()
def run(cmd):
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=120);return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def du_rows(path,depth):
    p=subprocess.run(['du','-x','-B1','--max-depth='+str(depth),str(path)],capture_output=True,text=True,timeout=150)
    rows=[]
    for line in p.stdout.splitlines():
        try:b,n=line.split('\t',1);rows.append({'bytes':int(b),'path':n})
        except ValueError:pass
    return {'exit_code':p.returncode,'top':sorted(rows,key=lambda x:x['bytes'],reverse=True)[:65],'stderr':p.stderr[:1500]}
large=[];arena=[];counts=collections.Counter();total_files=0
for current,dirs,files in os.walk(base,followlinks=False):
    dirs[:]=[d for d in dirs if not pathlib.Path(current,d).is_symlink()]
    for name in files:
        p=pathlib.Path(current,name)
        try:s=p.lstat()
        except FileNotFoundError:continue
        if not stat.S_ISREG(s.st_mode):continue
        total_files+=1;counts[p.suffix.lower()]+=s.st_size
        if s.st_size>=64*1024**2:large.append({'path':str(p),'bytes':s.st_size,'allocated':s.st_blocks*512,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'nlink':s.st_nlink})
        if 'shared_cpu' in p.parts or p.suffix in ('.mmap','.arena'):arena.append({'path':str(p),'bytes':s.st_size,'allocated':s.st_blocks*512})
procs=[]
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        comm=(proc/'comm').read_text().strip()
        if any(x in comm.lower() for x in ('python','rerun','rsync','tar','zip','gzip','git','scp','wget','curl','conda','pip')):
            raw=(proc/'cmdline').read_bytes().replace(b'\x00',b' ')
            procs.append({'pid':int(proc.name),'comm':comm,'model_or_experiment_cmd':any(x in raw for x in (b'native_driver',b'tracker',b'run_segment',b'run_native',b'execute_phase',b'fit3d',b'metric3d')),'cmd_sha256':__import__('hashlib').sha256(raw).hexdigest()})
    except (FileNotFoundError,PermissionError):pass
caches={}
for path in ('/root/.cache','/root/.conda/pkgs','/opt/conda/pkgs','/root/miniconda3/pkgs','/var/cache/apt/archives','/tmp'):
    p=pathlib.Path(path)
    if p.is_dir():caches[path]={'disk':shutil.disk_usage(p)._asdict(),'du':du_rows(p,2)}
print(json.dumps({'time_unix':time.time(),'hostname':socket.gethostname(),'data_disk':shutil.disk_usage(base)._asdict(),'shm':shutil.disk_usage('/dev/shm')._asdict(),'mounts':run(['findmnt','-T',str(base)]),'data_usage':du_rows(base,2),'large_files':sorted(large,key=lambda x:x['allocated'],reverse=True)[:160],'arena_files':arena,'file_count':total_files,'suffix_logical_bytes':dict(counts.most_common(20)),'processes':procs,'caches':caches},ensure_ascii=False))
