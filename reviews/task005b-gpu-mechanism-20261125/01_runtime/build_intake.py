import pathlib,json,subprocess,os
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');out={}
for f in ['configs/identity_lock.json','evidence/CPU_STAGE_RELEASE.json','overlay/io_import_overlay.py','overlay/gamecam_io_overlay.py','overlay/sitecustomize.py']:
 p=r/f;out[f]=p.read_text()
out['nvcc']=subprocess.run(['sh','-c','command -v nvcc || true'],capture_output=True,text=True).stdout
out['cuda_candidates']=[str(p) for parent in ['/opt','/usr/local','/root/rivermind-data'] for p in pathlib.Path(parent).glob('*') if any(s in p.name.lower() for s in ['cuda','toolchain','gamecam'])]
print(json.dumps(out))
