import pathlib,json,hashlib,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
files=['sitecustomize.py','source_candidate/runner/run_native_stage.py','source_candidate/native_control/install.py','overlay/runtime_io.py','source_candidate/native_control/stage_authorization.py','configs/LOCK.json','attempts/capture/C0_RECEIPT.json']
out={}
for f in files:
 p=r/f
 out[f]={'exists':p.exists()}
 if p.is_file():
  raw=p.read_bytes();out[f].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),text=raw.decode() if len(raw)<18000 else 'TOO_LARGE')
out['config_files']=[str(p) for p in (r/'configs').glob('*')]
out['operational']=[p.name for p in (r/'operational').glob('*')]
out['overlay']=[p.name for p in (r/'overlay').glob('*')]
out['python_present']=pathlib.Path('/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python').exists()
out['schedule']={m:[{'name':p.name,'bytes':p.stat().st_size} for p in (r/'attempts'/m).glob('*') if p.name in ('schedule.jsonl','SUCCESS.json','RESTORE_RECEIPT.json')] for m in ['B1','B4']}
print(json.dumps(out))
