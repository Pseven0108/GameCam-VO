import hashlib,json,os,pathlib,stat,time
base=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/download_cache/conda-pkgs')
envbase=pathlib.Path('/opt/gamecam-viper-fullseq-3090-20261120-061408/envs');rows=[];bad=[]
for env in sorted(envbase.iterdir()):
    meta=env/'conda-meta'
    if not meta.is_dir():continue
    for m in meta.glob('*.json'):
        doc=json.loads(m.read_text());source=doc.get('link',{}).get('source','')
        if not source.startswith(str(base)+'/'):continue
        source=pathlib.Path(source);checked=0;missing=[];inside=[];regular=[]
        for rel in doc.get('files',[]):
            p=env/rel;checked+=1
            if not p.exists() and not p.is_symlink():missing.append(rel);continue
            try:resolved=p.resolve(strict=True)
            except (OSError,RuntimeError):bad.append(str(p));continue
            if str(resolved).startswith(str(base)+'/'):inside.append({'path':str(p),'target':str(resolved)})
            if p.is_file() and not p.is_symlink():regular.append(str(p))
        rows.append({'prefix':str(env),'metadata':str(m),'package':doc.get('name'),'version':doc.get('version'),'link':doc.get('link'),'file_count':checked,'missing':missing,'runtime_files_resolving_inside_cache':inside,'ordinary_installed_file_count':len(regular)})
links=[];files=[]
for root,dirs,names in os.walk(base,followlinks=False):
    for n in dirs+names:
        p=pathlib.Path(root,n);s=p.lstat()
        if stat.S_ISLNK(s.st_mode):links.append({'path':str(p),'target':os.readlink(p)})
    for n in names:
        p=pathlib.Path(root,n);s=p.lstat()
        if not stat.S_ISREG(s.st_mode):continue
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
        files.append({'path':str(p),'relative_path':str(p.relative_to(base)),'bytes':s.st_size,'allocated':s.st_blocks*512,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode,'nlink':s.st_nlink,'device':s.st_dev,'sha256':h.hexdigest()})
refs=[]
for p in pathlib.Path('/etc/ld.so.conf.d').glob('*'):
    if p.is_file() and str(base) in p.read_text(errors='replace'):refs.append(str(p))
for name in ('LD_LIBRARY_PATH','LD_PRELOAD','CUDA_HOME','CONDA_PKGS_DIRS','TMPDIR'):
    if str(base) in os.environ.get(name,''):refs.append('environment:'+name)
for pid in pathlib.Path('/proc').iterdir():
    if not pid.name.isdigit():continue
    try:
        for n in ('cmdline','environ','maps'):
            data=(pid/n).read_bytes()
            if str(base).encode() in data:refs.append({'pid':pid.name,'reference_kind':n,'self':int(pid.name)==os.getpid()})
        for fd in (pid/'fd').iterdir():
            try:t=os.readlink(fd)
            except (FileNotFoundError,PermissionError):continue
            if t.startswith(str(base)+'/'):refs.append({'pid':pid.name,'reference_kind':'open_fd','target':t})
    except (FileNotFoundError,PermissionError):continue
print(json.dumps({'time_unix':time.time(),'root':str(base),'conda_environment_installation_audit':rows,'cache_files':files,'cache_symlinks':links,'total_logical_bytes':sum(x['bytes'] for x in files),'total_allocated_bytes':sum(x['allocated'] for x in files),'runtime_references':refs,'unresolved_environment_paths':bad}))
