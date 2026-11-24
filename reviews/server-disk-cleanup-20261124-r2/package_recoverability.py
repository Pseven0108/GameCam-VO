import hashlib,json,os,pathlib,stat,tarfile,time
root=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/download_cache/conda-pkgs');packages=[];all_delete=[]
def sha_stream(f):
    h=hashlib.sha256();size=0
    for b in iter(lambda:f.read(8*1024**2),b''):size+=len(b);h.update(b)
    return h.hexdigest(),size
for package in sorted(root.iterdir()):
    if not package.is_dir() or package.is_symlink() or package.name=='cache':continue
    archive=root/(package.name+'.tar.bz2');assert archive.is_file() and not archive.is_symlink(),str(package)
    with archive.open('rb') as f:archive_hash,archive_bytes=sha_stream(f)
    members={}
    with tarfile.open(archive,'r:bz2') as t:
        for member in t:
            rel=str(pathlib.PurePosixPath(member.name));p=package/rel
            assert not pathlib.PurePosixPath(rel).is_absolute() and '..' not in pathlib.PurePosixPath(rel).parts
            if member.isfile():
                with t.extractfile(member) as f:h,n=sha_stream(f)
                members[rel]={'kind':'file','sha256':h,'bytes':n}
            elif member.issym():members[rel]={'kind':'symlink','target':member.linkname}
            elif member.islnk():members[rel]={'kind':'hardlink','target':member.linkname}
    good=[];unrecoverable=[];post_install=[]
    for current,dirs,files in os.walk(package,followlinks=False):
        for name in files+[x for x in dirs if pathlib.Path(current,x).is_symlink()]:
            p=pathlib.Path(current,name);s=p.lstat();rel=str(p.relative_to(package));m=members.get(rel)
            row={'path':str(p),'relative_path':str(p.relative_to(root)),'bytes':s.st_size,'allocated':s.st_blocks*512,'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns,'nlink':s.st_nlink,'mode':s.st_mode,'package_archive':str(archive),'package_archive_sha256':archive_hash}
            if p.is_symlink():
                row.update(kind='symlink',target=os.readlink(p))
                if m and m['kind']=='symlink' and m['target']==row['target']:good.append(row)
                else:unrecoverable.append(row)
            elif p.is_file():
                with p.open('rb') as f:h,n=sha_stream(f)
                row.update(kind='file',sha256=h)
                if m and m['kind']=='file' and m['sha256']==h and m['bytes']==n:good.append(row)
                elif n<1024**2:post_install.append(row)
                else:unrecoverable.append(row)
            else:raise RuntimeError(str(p))
    packages.append({'package':package.name,'archive':str(archive),'archive_sha256':archive_hash,'archive_bytes':archive_bytes,'archive_all_members_read':True,'recoverable_count':len(good),'post_install_small_files_retained':post_install,'unrecoverable_retained':unrecoverable})
    all_delete.extend(good)
print(json.dumps({'time_unix':time.time(),'root':str(root),'packages':packages,'delete_candidates':all_delete,'candidate_count':len(all_delete),'candidate_allocated_bytes':sum(x['allocated'] for x in all_delete),'original_compressed_archives_retained':True,'deletion_performed':False}))
