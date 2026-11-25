"""Read current owning sources/compiler records; no GPU context."""
import pathlib,json,hashlib,subprocess,shutil
BASE=pathlib.Path('/root/rivermind-data')
OLD=BASE/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
NATIVE=BASE/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W'
HIST=BASE/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/source_candidate'
out={'files':{},'commands':{}}
for p in [NATIVE/'src/lib/droid_kernels.cu',NATIVE/'src/lib/droid.cpp',NATIVE/'setup.py',OLD/'candidate/task005b_kernels.cu',OLD/'candidate/task005b_bindings.cpp',OLD/'build_attempt02/build.ninja',BASE/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1/build/build.ninja']:
 if p.is_file():
  b=p.read_bytes();out['files'][str(p)]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'text':b.decode() if p.name in ('setup.py','build.ninja') else None}
def extract(s,n):
 start=s.index(n);return s[start:s.index('\n}\n',start)+3]
original=(NATIVE/'src/lib/droid_kernels.cu').read_text()
candidate=(OLD/'candidate/task005b_kernels.cu').read_text()
signatures=['std::vector<torch::Tensor> ba_cuda(','__global__ void linear_transform_kernel(','__global__ void uncertainty_update_kernel(','__global__ void dino_feats_projective_transform_kernel(']
out['function_comparison']={n:{'text_identical':extract(original,n)==extract(candidate,n),'native_SHA':hashlib.sha256(extract(original,n).encode()).hexdigest(),'candidate_SHA':hashlib.sha256(extract(candidate,n).encode()).hexdigest()} for n in signatures}
for label,argv in {'native_head':['git','-C',str(NATIVE),'rev-parse','HEAD'],'native_status':['git','-C',str(NATIVE),'status','--porcelain'],'g++':['g++','--version'],'nvcc':['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/cuda118/bin/nvcc','--version']}.items():
 p=subprocess.run(argv,capture_output=True,text=True,timeout=30);out['commands'][label]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
print(json.dumps(out,indent=2))
