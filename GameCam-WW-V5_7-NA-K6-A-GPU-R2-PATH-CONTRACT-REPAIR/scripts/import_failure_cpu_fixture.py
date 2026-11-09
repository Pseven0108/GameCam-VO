"""Failure publication fixture: CPU only, synthetic permission, no Torch import."""
import argparse,os,pathlib,traceback
from diagnostic_early_failure import publish_pre_model_failure
from model_io_boundary_v2 import ModelIOBoundary
p=argparse.ArgumentParser();p.add_argument('--out');p.add_argument('--session');p.add_argument('--mode');a=p.parse_args();root=pathlib.Path(a.out);out=root/'model';out.mkdir(mode=0o700);assert os.environ['CUDA_VISIBLE_DEVICES']==''
boundary=ModelIOBoundary([],[],[],[out],worker_files=[root/'worker_terminal.json'],worker_atomic_files=[root/'worker_terminal.json'],worker_root=root);boundary.install()
try:
 if a.mode=='original_boundary':(root/'pycache/torch.pyc').read_bytes()
 else:raise ImportError('CPU_INJECTED_EARLY_IMPORT_FAILURE')
except BaseException as e:
 traceback.print_exc();publish_pre_model_failure({},out,root,a.session,e,'TORCH_IMPORT',boundary)
 raise SystemExit(2)
