import os,sys,pathlib,json,time,hashlib,subprocess,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1]
HIST=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
out=ROOT/'build';out.mkdir(exist_ok=False)
start=time.time()
try:
 prefix=pathlib.Path(sys.prefix)
 cuda=next((p for p in [prefix,pathlib.Path('/usr/local/cuda-11.8')] if (p/'bin/nvcc').is_file()),None)
 if cuda is None: raise RuntimeError('Matching CUDA11.8 compiler unavailable; do not change environment')
 os.environ['CUDA_HOME']=str(cuda);os.environ['MAX_JOBS']='1';os.environ['TORCH_CUDA_ARCH_LIST']='8.6';os.environ['PATH']=str(cuda/'bin')+':'+os.environ['PATH']
 import torch
 from torch.utils.cpp_extension import load
 assert torch.version.cuda=='11.8',torch.version.cuda
 print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'CUDA_HOME':str(cuda),'context_initialized':torch.cuda.is_initialized()}),flush=True)
 m=load(name='gamecam_task005b_depth_paths',sources=[str(ROOT/'candidate/task005b_bindings.cpp'),str(ROOT/'candidate/task005b_kernels.cu')],extra_include_paths=[str(HIST/'source_candidate/thirdparty/lietorch/eigen')],extra_cflags=['-O3'],extra_cuda_cflags=['-O3'],build_directory=str(out),verbose=True)
 result={'PASS':True,'module':m.__file__,'sha256':hashlib.sha256(pathlib.Path(m.__file__).read_bytes()).hexdigest(),'seconds':time.time()-start,'context_initialized':torch.cuda.is_initialized(),'native_calls':0}
 (out/'BUILD_COMPLETE.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
except BaseException as e:
 traceback.print_exc();(out/'BUILD_FAILED.json').write_text(json.dumps({'error':repr(e),'seconds':time.time()-start}));raise
