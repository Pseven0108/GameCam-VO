import pathlib,json,subprocess,shutil,hashlib
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');hist=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/source_candidate')
out={}
for name in ['checkpoint/rng_state.py','run.py']:
 p=hist/name;raw=p.read_text();out[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source':raw if name.endswith('rng_state.py') else '\n'.join(raw.splitlines()[max(0,next(i for i,l in enumerate(raw.splitlines()) if 'def setup_seed' in l)-3):next(i for i,l in enumerate(raw.splitlines()) if 'def setup_seed' in l)+25])}
p=r/'snapshots/D1_S1_RGB019/manifest.json';m=json.loads(p.read_text());out['manifest_keys']=list(m);out['manifest']=m
out['source_HEAD']=subprocess.check_output(['git','-C',str(hist),'rev-parse','HEAD'],text=True).strip();out['source_status']=subprocess.check_output(['git','-C',str(hist),'status','--porcelain'],text=True)
out['gpu_processes']=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader'],text=True)
out['disk_free']=shutil.disk_usage(r).free;out['shm_free']=shutil.disk_usage('/dev/shm').free
print(json.dumps(out))
