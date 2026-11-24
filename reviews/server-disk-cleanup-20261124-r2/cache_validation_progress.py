import json,os,pathlib,time
rows=[]
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        cmd=(proc/'cmdline').read_bytes()
        if b'python' not in cmd:continue
        files=[]
        for fd in (proc/'fd').iterdir():
            try:t=os.readlink(fd)
            except (OSError,FileNotFoundError):continue
            if 'conda-pkgs' in t:files.append({'path':t,'position':(proc/'fdinfo'/fd.name).read_text().splitlines()[0]})
        if files:rows.append({'pid':int(proc.name),'open_cache_files':files})
    except (FileNotFoundError,PermissionError):pass
print(json.dumps({'time_unix':time.time(),'active_cache_verification':rows}))
