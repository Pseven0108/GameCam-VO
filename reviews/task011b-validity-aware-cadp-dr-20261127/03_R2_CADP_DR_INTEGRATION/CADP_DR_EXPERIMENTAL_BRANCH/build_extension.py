"""Compile only the isolated candidate, never install over droid_backends."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--upstream',required=True,type=Path)
    parser.add_argument('--build-dir',required=True,type=Path)
    args=parser.parse_args()
    import torch
    from torch.utils.cpp_extension import load
    if not torch.cuda.is_available() or torch.cuda.get_device_capability()!=(8,6):
        raise RuntimeError('TASK011B formal compilation/validation requires the allocated Ampere GPU; do not switch protocols')
    if args.build_dir.exists():raise RuntimeError('Use a new unique build directory; preserve prior attempt')
    args.build_dir.mkdir(parents=True)
    os.environ['TORCH_CUDA_ARCH_LIST']='8.6';os.environ['MAX_JOBS']='2'
    native=Path(__file__).parent/'native'
    extension=load(name='task011b_cadp_dr_c3414af6',build_directory=str(args.build_dir),
        sources=[str(native/n) for n in ('droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu')],
        extra_include_paths=[str(args.upstream/'thirdparty/lietorch/eigen')],
        extra_cflags=['-O3'],extra_cuda_cflags=['-O3'],verbose=True)
    (args.build_dir/'BUILD_RECEIPT.json').write_text(json.dumps(dict(status='BUILT_NOT_YET_REGRESSION_VALIDATED',
        module=extension.__file__,torch=torch.__version__,cuda=torch.version.cuda,
        GPU=torch.cuda.get_device_name(),upstream_installed_module_replaced=False),indent=2))


if __name__=='__main__':main()
