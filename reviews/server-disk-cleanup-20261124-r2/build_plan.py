import hashlib,json,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parent
recover=json.loads((ROOT/'package_recoverability.stdout.json').read_text())
verified=json.loads((ROOT/'DUPLICATE_ARCHIVES_LOCAL_VERIFICATION.json').read_text())
cache=json.loads((ROOT/'cache_audit.stdout.json').read_text())
assert recover['original_compressed_archives_retained']
assert not cache['runtime_references'] and not cache['unresolved_environment_paths']
assert all(not p['missing'] and not p['runtime_files_resolving_inside_cache'] for p in cache['conda_environment_installation_audit'])
rows=[]
for r in recover['delete_candidates']:rows.append({**r,'category':'RECONSTRUCTIBLE_EXTRACTED_INSTALL_CACHE'})
for r in verified:rows.append({**r,'kind':'file','category':'DUPLICATE_ARCHIVE_WITH_VERIFIED_LOCAL_COPY'})
assert len({r['path'] for r in rows})==len(rows)
plan={'time_unix':time.time(),'expected_hostname':json.loads((ROOT/'inventory.stdout.json').read_text())['hostname'],'cache_root':cache['root'],'delete_files':rows,'expected_allocated_bytes_reclaimed':sum(r['allocated'] for r in rows),'protected_real_C0':True,'protected_failed_Arenas':True,'original_package_archives_retained':True,'no_GPU_or_model_execution':True}
(ROOT/'CLEANUP_PLAN.json').write_text(json.dumps(plan,indent=2))
code=r'''
import hashlib,json,os,pathlib,shutil,socket,stat,sys,time
BASE=pathlib.Path('/root/rivermind-data');CACHE=pathlib.Path(PLAN['cache_root']);rows=PLAN['delete_files']
assert socket.gethostname()==PLAN['expected_hostname']
assert BASE.resolve()==BASE and CACHE.resolve()==CACHE and CACHE.is_relative_to(BASE)
expected={r['path'] for r in rows}
assert len(rows)==len(expected)
def sha(p):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);h=hashlib.sha256()
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno())
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
        b=os.fstat(f.fileno());assert (a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
    return h.hexdigest()
def users():
    found=[]
    for pid in pathlib.Path('/proc').iterdir():
        if not pid.name.isdigit():continue
        try:
            for fd in (pid/'fd').iterdir():
                try:target=os.readlink(fd)
                except (FileNotFoundError,PermissionError):continue
                if target in expected or target.removesuffix(' (deleted)') in expected:found.append((pid.name,target))
            for line in (pid/'maps').read_text(errors='replace').splitlines():
                parts=line.split(None,5)
                if len(parts)==6 and parts[5].removesuffix(' (deleted)') in expected:found.append((pid.name,parts[5]))
        except (FileNotFoundError,ProcessLookupError):pass
    return found
validated=[];removed=[];error=None;before=shutil.disk_usage(BASE)._asdict()
try:
    assert not users(),'A target is open/mapped; stop before deletion'
    source_archives={r['package_archive']:r['package_archive_sha256'] for r in rows if r['category']=='RECONSTRUCTIBLE_EXTRACTED_INSTALL_CACHE'}
    for name,expected_hash in source_archives.items():
        p=pathlib.Path(name);assert p.parent==CACHE and not p.is_symlink() and p.name.endswith('.tar.bz2') and sha(p)==expected_hash
    for r in rows:
        p=pathlib.Path(r['path']);assert p.is_absolute() and p.is_relative_to(BASE) and p.parent.resolve(strict=True)==p.parent
        s=p.lstat();assert (s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)==(r['inode'],r['bytes'],r['mtime_ns'],r['nlink'])
        if r['category']=='RECONSTRUCTIBLE_EXTRACTED_INSTALL_CACHE':
            assert p.is_relative_to(CACHE) and len(p.relative_to(CACHE).parts)>=2
        else:
            assert r['local_sha256']==r['sha256'] and r['archive_integrity'] in ('ZIP_CRC_PASS','TAR_FULL_MEMBER_READ_PASS')
            assert p.suffix in ('.zip','.tar','.gz')
        if r['kind']=='file':assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and sha(p)==r['sha256']
        else:assert stat.S_ISLNK(s.st_mode) and os.readlink(p)==r['target']
        validated.append(r['path'])
    assert len(validated)==len(rows) and not users()
    for r in rows:
        p=pathlib.Path(r['path']);s=p.lstat()
        assert (s.st_ino,s.st_size,s.st_mtime_ns,s.st_nlink)==(r['inode'],r['bytes'],r['mtime_ns'],r['nlink'])
        assert p.parent.resolve(strict=True)==p.parent
        p.unlink();removed.append({'path':str(p),'bytes':r['bytes'],'allocated':r['allocated'],'category':r['category'],'sha256':r.get('sha256'),'local_backup':r.get('local_backup'),'package_archive':r.get('package_archive')})
        assert not p.exists() and not p.is_symlink()
    os.sync()
except BaseException as exc:error=repr(exc)
after=shutil.disk_usage(BASE)._asdict()
print(json.dumps({'time_unix':time.time(),'hostname':socket.gethostname(),'before':before,'after':after,'actual_free_increase_bytes':after['free']-before['free'],'validated_count':len(validated),'removed_count':len(removed),'removed':removed,'error':error,'GPU_initialized':False,'model_loaded':False,'shutdown_performed':False,'reboot_performed':False},separators=(',',':')),flush=True)
if error:sys.exit(1)
'''
(ROOT/'execute_cleanup.py').write_text('PLAN='+repr(plan)+'\n'+code)
print(json.dumps({'candidate_count':len(rows),'estimated_reclaim_GiB':plan['expected_allocated_bytes_reclaimed']/2**30,'regular_cache_count':sum(r['kind']=='file' and r['category'].startswith('RECONSTRUCTIBLE') for r in rows),'symlink_cache_count':sum(r['kind']=='symlink' for r in rows),'duplicate_archive_count':len(verified)},indent=2))
