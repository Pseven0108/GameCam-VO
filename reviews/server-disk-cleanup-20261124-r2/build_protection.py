import json,pathlib
root=pathlib.Path(__file__).resolve().parent
prior=pathlib.Path(r'D:\aaa\GameCam-VO\maintenance\DATA_DISK_CLEANUP_20261124')
pins=json.loads((prior/'protected_pins.json').read_text())
cache=json.loads((root/'cache_audit.stdout.json').read_text())
code=r'''
import hashlib,json,os,pathlib,shutil,socket,stat,subprocess,time
BASE=pathlib.Path('/root/rivermind-data');TASK=BASE/'DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1'
assert BASE.resolve()==BASE and socket.gethostname()==EXPECTED_HOSTNAME
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
files={};errors=[]
for current,dirs,names in os.walk(BASE,followlinks=False,onerror=lambda e:errors.append(str(e))):
    for name in names+[d for d in dirs if pathlib.Path(current,d).is_symlink()]:
        p=pathlib.Path(current,name)
        try:s=p.lstat();files[str(p)]=[s.st_mode,s.st_size,s.st_ino,s.st_mtime_ns,s.st_nlink,os.readlink(p) if p.is_symlink() else None]
        except OSError as e:errors.append(str(e))
assert not errors,errors
protected={}
def add(p,expected=None):
    p=pathlib.Path(p);s=p.stat();actual=sha(p)
    if expected:assert actual==expected,(str(p),actual)
    protected[str(p)]={'bytes':s.st_size,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'sha256':actual}
for name,expected in PINS.items():add(name,expected)
for group in ('C0','configs','source_candidate/native_control','source_candidate/checkpoint'):
    for p in sorted((TASK/group).rglob('*')):
        if p.is_file() and not p.is_symlink():add(p)
for inputroot in (BASE/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/val_007',BASE/'DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487'):
    images=[p for p in inputroot.rglob('*') if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png')]
    assert len(images)==487
    for p in sorted(images):add(p)
arenas=[]
for path in files:
    p=pathlib.Path(path)
    if 'shared_cpu' in p.parts and p.is_file() and not p.is_symlink():add(p);arenas.append(path)
installed_files=set()
for r in PACKAGE_AUDIT:
    meta=pathlib.Path(r['metadata']);add(meta)
    d=json.loads(meta.read_text());env=pathlib.Path(r['prefix'])
    for rel in d.get('files',[]):
        p=env/rel
        assert p.exists(),str(p)
        assert not str(p.resolve()).startswith(CACHE_ROOT+'/')
        if p.is_file():installed_files.add(str(p))
for path in sorted(installed_files):add(path)
C=json.loads((TASK/'C0/manifest.json').read_text());assert C['state_sha256']=='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
source=TASK/'source_candidate';commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();status=subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True)
assert commit=='5d357c1d3079de134dd8b41a20a00632da37f0b0' and not status
print(json.dumps({'time_unix':time.time(),'hostname':socket.gethostname(),'disk':shutil.disk_usage(BASE)._asdict(),'files':files,'protected_hashes':protected,'protected_hash_count':len(protected),'arena_paths':arenas,'installed_cuda_files_hashed':len(installed_files),'C0_state_sha256':C['state_sha256'],'source_commit':commit,'source_clean':not status},separators=(',',':')))
'''
preamble='PINS='+repr(pins)+'\nEXPECTED_HOSTNAME='+repr(json.loads((root/'inventory.stdout.json').read_text())['hostname'])+'\nPACKAGE_AUDIT='+repr(cache['conda_environment_installation_audit'])+'\nCACHE_ROOT='+repr(cache['root'])+'\n'
(root/'protection_template.py').write_text(preamble+code)
(root/'protection_before.py').write_text(preamble+code)
