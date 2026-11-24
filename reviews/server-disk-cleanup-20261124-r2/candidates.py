import hashlib,json,os,pathlib,shutil,stat,subprocess,time
base=pathlib.Path('/root/rivermind-data');cache=base/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/download_cache';pkgs=cache/'conda-pkgs'
def info(p,do_hash=False):
    s=p.lstat();r={'path':str(p),'bytes':s.st_size,'allocated':s.st_blocks*512,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'nlink':s.st_nlink,'mode':s.st_mode,'symlink':p.is_symlink()}
    if do_hash and stat.S_ISREG(s.st_mode):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
        r['sha256']=h.hexdigest()
    return r
archives=[];extracted={};cache_top=[]
for p in cache.iterdir():
    cache_top.append(info(p))
for p in pkgs.rglob('*'):
    if p.is_symlink():continue
    if p.is_file():
        if p.name.endswith(('.tar.bz2','.conda','.whl','.zip','.tmp','.part')) or p.parent.name=='cache':archives.append(info(p,True))
        else:
            name=p.relative_to(pkgs).parts[0];v=extracted.setdefault(name,{'files':0,'bytes':0,'allocated_unique_bytes':0,'multiply_linked_files':0,'symlinks_to_package':[]});s=p.stat();v['files']+=1;v['bytes']+=s.st_size
            if s.st_nlink==1:v['allocated_unique_bytes']+=s.st_blocks*512
            else:v['multiply_linked_files']+=1
refs=[];env_roots=[]
for start in (pathlib.Path('/opt'),pathlib.Path('/usr/local')):
    if not start.is_dir():continue
    for root,dirs,files in os.walk(start,followlinks=False):
        depth=len(pathlib.Path(root).relative_to(start).parts)
        if depth>8:dirs[:]=[];continue
        for name in dirs+files:
            p=pathlib.Path(root,name)
            if p.is_symlink():
                try:resolved=str(p.resolve())
                except (OSError,RuntimeError):continue
                if resolved.startswith(str(pkgs)+'/'):refs.append({'symlink':str(p),'target':resolved})
        if pathlib.Path(root).name=='conda-meta':env_roots.append(str(pathlib.Path(root).parent));dirs[:]=[]
        if pathlib.Path(root).name in ('site-packages','.git','include'):dirs[:]=[]
other_archives=[]
for root,dirs,files in os.walk(base,followlinks=False):
    dirs[:]=[d for d in dirs if d not in ('.git','storages','datasets','data','inputs','source_candidate','source','shared_cpu','conda-pkgs')]
    for name in files:
        if name.endswith(('.zip','.tar.gz','.tar','.tgz','.tar.bz2','.conda','.whl','.run')):
            p=pathlib.Path(root,name)
            if p.is_file() and not p.is_symlink() and p.stat().st_size>=5*1024**2:other_archives.append(info(p,True))
print(json.dumps({'time_unix':time.time(),'cache_top':cache_top,'archive_candidates':archives,'archive_bytes':sum(x['allocated'] for x in archives),'extracted_cache_summary':extracted,'external_symlinks_into_pkgs':refs,'environment_roots':env_roots,'other_archives':other_archives},ensure_ascii=False))
