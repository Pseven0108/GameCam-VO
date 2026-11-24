import base64,hashlib,json,pathlib,shlex,shutil,subprocess,sys,tarfile,time
from remote_access import ROOT,ssh,pre
cache=json.loads((ROOT/'cache_audit.stdout.json').read_text())
assert not cache['runtime_references'] and not cache['unresolved_environment_paths']
assert all(not r['missing'] and not r['runtime_files_resolving_inside_cache'] for r in cache['conda_environment_installation_audit'])
assert shutil.disk_usage(ROOT).free>cache['total_logical_bytes']+2*1024**3
code=r"""
import gzip,json,os,pathlib,sys,tarfile,time
root=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/download_cache/conda-pkgs')
assert root.is_dir() and not root.is_symlink()
with gzip.GzipFile(fileobj=sys.stdout.buffer,mode='wb',compresslevel=1) as gz, tarfile.open(fileobj=gz,mode='w|') as t:
    t.add(root,arcname='conda-pkgs',recursive=True)
print(json.dumps({'complete':True,'time_unix':time.time(),'source_root':str(root)}),file=sys.stderr)
"""
base=ssh.ssh_base(pre);base[base.index('-p')+1]='REDACTED_SSH_PORT'
loader='import base64;exec(compile(base64.b64decode('+repr(base64.b64encode(code.encode()).decode())+'),"<cache-backup>","exec"))'
cmd='exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -u -c '+shlex.quote(loader)
archive=ROOT/'conda_package_cache_backup_v2.tar.gz';err=ROOT/'cache_backup_v2.stderr.txt';started=time.time()
with archive.open('xb') as out,err.open('xb') as log:
    p=subprocess.run(base+['-o','ClearAllForwardings=yes',ssh.HOST,cmd],stdout=out,stderr=log,timeout=1500,creationflags=ssh.CREATE)
trust=ssh.verified(err);assert p.returncode==0 and all(trust.values())
expected={x['relative_path']:x for x in cache['cache_files']};seen=set();links=[]
with tarfile.open(archive,'r:gz') as t:
    for m in t:
        if m.isdir():continue
        name=str(pathlib.PurePosixPath(m.name).relative_to('conda-pkgs'))
        if m.issym():links.append({'relative_path':name,'target':m.linkname});continue
        assert m.isfile() and name in expected and name not in seen
        h=hashlib.sha256();n=0
        with t.extractfile(m) as f:
            for b in iter(lambda:f.read(8*1024**2),b''):n+=len(b);h.update(b)
        assert n==expected[name]['bytes'] and h.hexdigest()==expected[name]['sha256'],name
        seen.add(name)
assert seen==set(expected)
expected_links={str(pathlib.PurePosixPath(r['path']).relative_to(cache['root'])):r['target'] for r in cache['cache_symlinks']}
assert {r['relative_path']:r['target'] for r in links}==expected_links
h=hashlib.sha256()
with archive.open('rb') as f:
    for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
receipt={'PASS':True,'source_root':cache['root'],'local_archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':h.hexdigest(),'regular_files_SHA256_verified':len(seen),'symlinks_verified':len(links),'tar_members_full_read':True,'cache_original_total_bytes':cache['total_logical_bytes'],'ssh_exit_code':p.returncode,'trust':trust,'started_unix':started,'ended_unix':time.time(),'deleted_remote_files':0}
(ROOT/'CACHE_LOCAL_BACKUP_VERIFICATION.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))

