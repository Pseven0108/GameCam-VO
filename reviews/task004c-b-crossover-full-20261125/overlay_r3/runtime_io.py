"""Allocation and artifact I/O only. No model, optimizer, RNG or BA changes."""
import os,pathlib,json,hashlib,shutil,stat
GIB=1024**3
CPU_BYTES=2246400000
TMPFS_BASE=pathlib.Path('/dev/shm/gamecam_task004cb_io_r3')

def arena_for(root,mode):
    if mode not in ('B1','B2','B4','B3'):raise RuntimeError('Formal-only I/O recovery grant')
    suffix=hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return TMPFS_BASE/(suffix+'_'+mode)

def configure_tmpfs_arena(root):
    root=pathlib.Path(root).resolve();out=pathlib.Path(os.environ['GAMECAM_NATIVE_ATTEMPT'])
    if out.parent!=root/'attempts':raise RuntimeError('Arena attempt ownership mismatch')
    path=arena_for(root,out.name)
    if TMPFS_BASE.exists():
        s=TMPFS_BASE.stat()
        if TMPFS_BASE.is_symlink() or s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700:raise RuntimeError('Unowned tmpfs namespace')
    else:TMPFS_BASE.mkdir(mode=0o700)
    os.environ['GAMECAM_FILE_BACKED_CPU_ROOT']=str(path)
    # The original FileArena creates this directory, reserves real bytes, validates
    # inode/size/mode and uses the same torch.from_file MAP_SHARED reducer.

def install_resource_accounting(root):
    from native_control import admission
    old=admission.continuation_preflight
    if getattr(old,'_gamecam_io_r3',False):return
    def check(root,release):
        a=old(root,release);issues=list(a['issues'])
        issue='DATA_DISK_BELOW_RESTORE_ARENA_LOGS_AND_FLOOR'
        if issue in issues:issues.remove(issue)
        if a['data_disk']['free']<11*GIB:issues.append('DATA_DISK_BELOW_OUTPUT_GIB_AND_10GIB_FLOOR')
        if a['shared_memory']['free']<10*GIB+CPU_BYTES+64*1024**2:issues.append('TMPFS_BELOW_ARENA_AND_10GIB_FLOOR')
        a.update(original_admission=a['admitted'],original_issues=a['issues'],issues=issues,admitted=not issues,
                 data_disk_output_reservation_bytes=GIB,arena_reservation_bytes=CPU_BYTES,
                 arena_backing='OWNED_FILE_MMAP_ON_EXISTING_TMPFS',safety_floor_bytes=10*GIB)
        return a
    check._gamecam_io_r3=True;admission.continuation_preflight=check

def install_lossless_video_io():
    import numpy as np
    original=np.savez
    if getattr(original,'_gamecam_lossless_video',False):raise RuntimeError('Artifact writer installed twice')
    def save(file,*args,**kwargs):
        if pathlib.Path(file).name=='video.npz':return np.savez_compressed(file,*args,**kwargs)
        return original(file,*args,**kwargs)
    save._gamecam_lossless_video=True;np.savez=save
    out=pathlib.Path(os.environ['GAMECAM_NATIVE_ATTEMPT'])
    hub=pathlib.Path(os.environ['TORCH_HOME'])
    cache={}
    for name in ('yvanyin_metric3d_main','ywyue_FiT3D_main'):
        p=hub/name/'hubconf.py'
        if not p.is_file():raise RuntimeError('Frozen local hub source missing')
        cache[name]={'hubconf_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    p=out/('RUNTIME_IO_R3_'+str(os.getpid())+'.json')
    with p.open('x') as f:json.dump({'scope':'ARTIFACT_SERIALIZATION_AND_LOCAL_ASSET_ROUTING_ONLY','hub_sources':cache,
        'numpy_video_writer':'numpy.savez_compressed','other_npz_writer':'original numpy.savez',
        'arena':os.environ['GAMECAM_FILE_BACKED_CPU_ROOT'],'optimizer_math_changed':False,'weights_changed':False},f,indent=2)
