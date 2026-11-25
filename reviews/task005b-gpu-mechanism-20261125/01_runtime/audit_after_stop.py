"""Verify frozen identities and actual resource/process status after guard stop."""
import pathlib,json,subprocess,hashlib,shutil,time
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')
history=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
lock=json.loads((history/'configs/identity_lock.json').read_text())
pins=[]
for name,expected in lock['remote_pins'].items():
    h=hashlib.sha256();p=pathlib.Path(name)
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024**2),b''):h.update(block)
    pins.append({'path':name,'bytes':p.stat().st_size,'sha256':h.hexdigest(),'expected_sha256':expected,'PASS':h.hexdigest()==expected})
def git(*args):return subprocess.check_output(['git','-C',str(history/'source_candidate'),*args],text=True).strip()
out={'unix':time.time(),'pins':pins,'all_protected_asset_hashes_match':all(x['PASS'] for x in pins),'source_HEAD':git('rev-parse','HEAD'),'source_status':git('status','--porcelain'),
     'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader'],text=True).strip(),
     'gpu_compute_processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader'],text=True).strip(),
     'disk_free_bytes':shutil.disk_usage(r).free,'shm_free_bytes':shutil.disk_usage('/dev/shm').free,
     'attempted_prefixes':sorted(x.name for x in (r/'attempts').iterdir()),'shutdown_performed':False,'automatic_retry':False}
assert out['all_protected_asset_hashes_match'] and not out['source_status'] and not out['gpu_compute_processes']
(r/'evidence/FROZEN_IDENTITY_AFTER_STOP.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
