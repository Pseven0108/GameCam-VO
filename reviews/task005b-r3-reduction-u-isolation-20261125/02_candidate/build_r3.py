import os,sys,pathlib,json,time,hashlib,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1]
HIST=ROOT.parent/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE'
out=ROOT/'build';out.mkdir(exist_ok=False);start=time.time()
try:
    prefix=pathlib.Path(sys.prefix)
    cuda=next((p for p in [prefix,prefix.parent/'cuda118',pathlib.Path('/usr/local/cuda-11.8')] if (p/'bin/nvcc').is_file()),None)
    assert cuda is not None
    os.environ.update(CUDA_HOME=str(cuda),MAX_JOBS='1',TORCH_CUDA_ARCH_LIST='8.6')
    os.environ['PATH']=str(cuda/'bin')+':'+os.environ['PATH']
    import torch
    from torch.utils.cpp_extension import load
    assert torch.version.cuda=='11.8'
    print(json.dumps({'torch':torch.__version__,'cuda_home':str(cuda),'cuda_initialized':torch.cuda.is_initialized()}),flush=True)
    module=load(name='gamecam_task005b_r3_isolation',sources=[str(ROOT/'candidate/task005b_r3_bindings.cpp'),str(ROOT/'candidate/task005b_r3_kernels.cu')],extra_include_paths=[str(HIST/'source_candidate/thirdparty/lietorch/eigen')],extra_cflags=['-O3'],extra_cuda_cflags=['-O3'],build_directory=str(out),verbose=True)
    proof={'PASS':True,'module':module.__file__,'sha256':hashlib.sha256(pathlib.Path(module.__file__).read_bytes()).hexdigest(),'seconds':time.time()-start,'cuda_initialized':torch.cuda.is_initialized(),'native_calls':0}
    (out/'BUILD_COMPLETE.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)
except BaseException as e:
    traceback.print_exc();(out/'BUILD_FAILED.json').write_text(json.dumps({'error':repr(e),'seconds':time.time()-start}));raise
