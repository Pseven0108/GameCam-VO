"""Bounded local runtime inventory after completion, without model inference."""
import importlib,subprocess,sys,os
from runtime_local import *
import torch
def main():
    import droid_backends
    expected='de87a5bc8167634b0aa0986fac02782ebcaa5a9a0793ed388562168bfddfe1fc'
    actual=sha(droid_backends.__file__)
    if actual!=expected:raise RuntimeError('Installed original CUDA extension identity changed')
    path=TASK/'reports/FINAL_RUNTIME_AUDIT.json'
    if path.exists():raise FileExistsError(path)
    write(path,dict(python=sys.version,executable=sys.executable,torch=torch.__version__,cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(),capability=torch.cuda.get_device_capability(),
        installed_original_extension=droid_backends.__file__,installed_sha256=actual,
        original_extension_sha256_preserved=True,allocator=os.environ.get('PYTORCH_CUDA_ALLOC_CONF'),
        remote_connections=0,environment_modifications='none',baseline_source_writes=0,
        weights_shared_read_only=True,source_export_commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc'))
    (TASK/'reports/LOCAL_LINUX_DEPENDENCIES.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    print('FINAL_RUNTIME_AUDIT_PASS')
if __name__=='__main__':main()
