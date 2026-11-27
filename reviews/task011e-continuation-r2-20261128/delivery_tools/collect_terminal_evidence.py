"""Copy the terminal R2 evidence over pinned SSH without remote staging writes."""
import hashlib, io, json, runpy, subprocess, tarfile
from pathlib import Path, PurePosixPath

BASE = Path(__file__).resolve().parent
CODE = r'''
from pathlib import Path
import gzip, hashlib, io, json, os, shutil, subprocess, sys, tarfile, time
root=Path('/root/rivermind-data/GAMECAM_TASK011E_FAST_20261128_R2')
task=root/'repo/experiments/TASK011E'
if not ((task/'BATCH_STOPPED.json').exists() or (task/'BATCH_TERMINAL.json').exists()):
    raise RuntimeError('Evidence seal requires a terminal batch; never interrupts or restarts it')
apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
if apps:raise RuntimeError('GPU process still active; wait for natural exit')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
items={}
for p in task.rglob('*'):
    rel=p.relative_to(task)
    if not p.is_file() or any(v in rel.parts for v in ('private','tmp','__pycache__','cache','fixed_state')):continue
    if p.suffix.lower() in ('.pt','.pth','.so','.pyc','.jpg','.jpeg','.png'):continue
    if p.stat().st_size>64*1024**2:raise RuntimeError('Unexpectedly large evidence file: '+str(rel))
    items['task/'+rel.as_posix()]=p
for p in root.glob('*'):
    if p.is_file() and p.suffix in ('.json','.txt','.log'):items['service/'+p.name]=p
cache_inventory=[]
for folder in sorted((task/'cache').iterdir()):
    if not folder.is_dir():continue
    for p in sorted(folder.glob('*.npz')):
        cache_inventory.append(dict(path=p.relative_to(task).as_posix(),bytes=p.stat().st_size,sha256=digest(p)))
    for p in folder.glob('*.json'):items['cache/'+folder.name+'/'+p.name]=p
snapshots=[]
for p in sorted((task/'fixed_state').rglob('*')) if (task/'fixed_state').exists() else []:
    if not p.is_file():continue
    rel=p.relative_to(task).as_posix()
    if p.suffix in ('.json','.jsonl','.txt'):items['task/'+rel]=p
    else:snapshots.append(dict(path=rel,bytes=p.stat().st_size,sha256=digest(p)))
fresh=Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
source=fresh/'source/DROID-W'
model=json.loads((task/'MODEL_WEIGHT_IDENTITY.json').read_text())
weights=[]
for entry in model['weights']:
    p=Path(entry['path']);actual=digest(p)
    weights.append(dict(name=entry['name'],bytes=p.stat().st_size,sha256=actual,
                        expected_sha256=entry['sha256'],match=actual==entry['sha256']))
source_lock=json.loads((task/'configs/UPSTREAM_PYTHON_IDENTITY.json').read_text())
source_results=[]
for entry in source_lock['files']:
    actual=digest(source/entry['path'])
    source_results.append(dict(path=entry['path'],sha256=actual,expected_sha256=entry['sha256'],
                               match=actual==entry['sha256']))
resources=dict(when_unix=time.time(),disk_free_bytes=shutil.disk_usage(task).free,
    shm_total_bytes=shutil.disk_usage('/dev/shm').total,
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.free','--format=csv,noheader'],text=True).strip(),
    gpu_compute_processes=apps,original_extension_sha256=digest(source/'droid_backends.cpython-310-x86_64-linux-gnu.so'),
    candidate_extension_sha256=digest(Path('/root/rivermind-data/GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/build_001/task011b_cadp_dr_c3414af6.so')),
    official_archive=json.loads((source/'.official_archive.json').read_text()),research_run_restarted=False,
    weights=weights,source_files=source_results,
    source_and_weights_preserved=all(r['match'] for r in weights+source_results))
generated={'CACHE_FILE_INVENTORY.json':cache_inventory,'SNAPSHOT_FILE_INVENTORY.json':snapshots,'FINAL_RESOURCE_STATUS.json':resources}
manifest=[]
with gzip.GzipFile(fileobj=sys.stdout.buffer,mode='wb',compresslevel=1) as gz:
    with tarfile.open(fileobj=gz,mode='w|') as tar:
        def add(name,raw):
            inf=tarfile.TarInfo(name);inf.size=len(raw);inf.mode=0o600
            tar.addfile(inf,io.BytesIO(raw))
            manifest.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        for name,path in sorted(items.items()):add(name,path.read_bytes())
        for name,value in generated.items():add(name,(json.dumps(value,indent=2)+'\n').encode())
        raw=(json.dumps(manifest,indent=2)+'\n').encode();inf=tarfile.TarInfo('TRANSFER_MANIFEST.json');inf.size=len(raw)
        tar.addfile(inf,io.BytesIO(raw))
'''

def main():
    target=BASE/'terminal_evidence'
    archive=BASE/'TERMINAL_EVIDENCE_TRANSFER.tar.gz'
    if target.exists() or archive.exists():raise FileExistsError('Preserve existing evidence transfer')
    api=runpy.run_path('D:/aaa/GameCam-VO-TASK011E/experiments/TASK011E/monitor_remote.py')
    with archive.open('xb') as out, (BASE/'EVIDENCE_TRANSFER_STDERR.txt').open('xb') as err:
        p=subprocess.run(api['command'](CODE),stdout=out,stderr=err,timeout=1200,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError('Terminal evidence transfer failed; partial file retained')
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        for member in members:
            rel=PurePosixPath(member.name)
            if not member.isfile() or rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe transfer member')
        records=json.load(tar.extractfile('TRANSFER_MANIFEST.json'))
        expected={r['path']:r for r in records}
        if set(expected)!={m.name for m in members if m.name!='TRANSFER_MANIFEST.json'}:raise ValueError('Incomplete transfer')
        target.mkdir()
        for member in members:
            raw=tar.extractfile(member).read()
            if member.name in expected:
                r=expected[member.name]
                if len(raw)!=r['bytes'] or hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('Transfer hash mismatch')
            dest=target.joinpath(*PurePosixPath(member.name).parts)
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    receipt=dict(status='PASS',files=len(records),archive_bytes=archive.stat().st_size,
                 archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),all_member_sha256_verified=True,
                 raw_cache_arrays_and_snapshots_preserved_on_server=True)
    (BASE/'TERMINAL_EVIDENCE_TRANSFER_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
