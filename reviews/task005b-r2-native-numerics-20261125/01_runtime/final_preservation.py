"""No GPU context: rehash protected state after all ten calls, save full logs."""
import pathlib,json,subprocess,hashlib,shutil
R=pathlib.Path('/root/rivermind-data')
OLD=R/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
NEW=R/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
HIST=R/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE'
NATIVE=R/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
files=list((OLD/'snapshots/D0_S1_RGB233').iterdir())+list((OLD/'build_attempt02').glob('*.so'))+[NATIVE/'droid_backends.cpython-310-x86_64-linux-gnu.so',HIST/'configs/LOCK.json']
for p in (HIST/'configs').glob('*.yaml'):files.append(p)
lock=json.loads((HIST/'configs/LOCK.json').read_text()) if (HIST/'configs/LOCK.json').exists() else {'status':'NOT_AT_LEGACY_PATH','path':str(HIST/'configs/LOCK.json')}
out={'files':{str(p):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files if p.is_file()},'lock':lock,'receipts':{},'disk_free':shutil.disk_usage(R).free,'new_directory_bytes':sum(p.stat().st_size for p in NEW.rglob('*') if p.is_file())}
for phase in ['plain','build','trace']:
 p=NEW/'evidence'/phase/'PROCESS_RECEIPT.json';out['receipts'][phase]=json.loads(p.read_text());assert out['receipts'][phase]['exit_code']==0
out['logs']={str(p.relative_to(NEW)):p.read_text() for p in (NEW/'evidence').rglob('*.txt') if p.stat().st_size<1000000}
for name,cmd in {'gpu_processes':['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],'gpu':['nvidia-smi','--query-gpu=name,uuid,memory.used,memory.free','--format=csv,noheader'],'historical_status':['git','-C',str(HIST/'source_candidate'),'status','--porcelain']}.items():
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=30);out[name]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
print(json.dumps(out,indent=2))
