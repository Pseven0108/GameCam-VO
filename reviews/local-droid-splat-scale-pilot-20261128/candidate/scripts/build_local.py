"""Build TASK011B's already audited A5 extension for the local sm_120 only."""
import json,os,pathlib,re
from runtime_local import ROOT,TASK,OLD,write,sha
import torch
from torch.utils.cpp_extension import load
build=ROOT/'toolchain/build/a5_sm120_001'
build.mkdir(parents=True,exist_ok=True)
# PyTorch2.7 removed the deprecated Tensor.type() dispatch conversion. Stage
# an isolated build copy with scalar_type(); kernel arithmetic is unchanged.
native=ROOT/'toolchain/native_api_compat'
native.mkdir(exist_ok=True)
patches=[]
for n in ['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']:
    old=(TASK/'native'/n).read_text()
    text=re.sub(r'AT_DISPATCH_FLOATING_TYPES\((\w+)\.type\(\)',r'AT_DISPATCH_FLOATING_TYPES(\1.scalar_type()',old)
    text=re.sub(r'AT_DISPATCH_FLOATING_TYPES_AND_HALF\((\w+)\.type\(\)',r'AT_DISPATCH_FLOATING_TYPES_AND_HALF(\1.scalar_type()',text)
    (native/n).write_text(text)
    if old!=text:patches.append(n)
gpu_include=list(pathlib.Path(torch.__file__).parents[1].glob('nvidia/*/include'))
module=load(name='local_a5_splat_c3414af6',build_directory=str(build),
    sources=[str(native/n) for n in ['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']],
    extra_include_paths=[str(OLD/'thirdparty/lietorch/eigen')]+[str(p) for p in gpu_include],
    extra_cflags=['-O3'],extra_cuda_cflags=['-O3'],verbose=True)
write(TASK/'reports/LOCAL_A5_BUILD.json',dict(status='BUILT_NOT_YET_NUMERICALLY_VERIFIED',
    torch=torch.__version__,cuda=torch.version.cuda,device=torch.cuda.get_device_name(),
    module=module.__file__,sha256=sha(module.__file__),installed_backend_replaced=False,
    API_only_scalar_type_compatibility=patches,kernel_arithmetic_changed=False))
print('LOCAL_A5_BUILD_COMPLETE',flush=True)
