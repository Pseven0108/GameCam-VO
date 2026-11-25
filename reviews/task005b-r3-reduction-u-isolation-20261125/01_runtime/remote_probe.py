"""Read-only R3 intake; no torch import, secret URLs, or process arguments."""
import pathlib,json,hashlib,subprocess,shutil
DATA=pathlib.Path('/root/rivermind-data')
R1=DATA/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
R2=DATA/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
ORIGINAL=DATA/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W/droid_backends.cpython-310-x86_64-linux-gnu.so'
HIST=DATA/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/source_candidate'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def cmd(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=30)
    return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
paths=[ORIGINAL]+list((R1/'snapshots/D0_S1_RGB233').iterdir())+list((R1/'build_attempt02').glob('*.so'))+list((R2/'build').glob('*.so'))+list((R2/'results/trace').glob('*.npz'))
files={str(p):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths if p.is_file()}
print(json.dumps({'gpu':cmd(['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader']),'compute_processes':cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),'disk':dict(zip(('total','used','free'),shutil.disk_usage(DATA))),'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'files':files,'historical_head':cmd(['git','-C',str(HIST),'rev-parse','HEAD']),'historical_status':cmd(['git','-C',str(HIST),'status','--porcelain']),'r3_exists':(DATA/'GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1').exists()},indent=2))
