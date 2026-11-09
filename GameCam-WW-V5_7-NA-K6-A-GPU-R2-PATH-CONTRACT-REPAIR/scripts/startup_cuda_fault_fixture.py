"""Isolated CUDA failure fixtures, never import DROID-W or deserialize weights."""
import argparse,os,pathlib,time,json,traceback
from startup_protocol import StartupReporter
from linux_safety import atomic_json
from native_linux_guard_v2 import Guard
from worker_terminal import publish_terminal
p=argparse.ArgumentParser();p.add_argument('--out');p.add_argument('--session');p.add_argument('--fault',default='api-error');a=p.parse_args();out=pathlib.Path(a.out)
reporter=StartupReporter(out,a.session).start();guard=None
try:
 import torch
 from types import SimpleNamespace
 guard=Guard(out,out,torch,a.session,execution_kind='cpu_dummy',diagnostic=SimpleNamespace(startup=reporter,emit=lambda *a,**kw:None))
 if a.fault=='heartbeat-stop':guard.hb.finish();time.sleep(10)
 try:torch.empty((-1,),device='cuda')
 except RuntimeError as exc:
  error='SYNTHETIC_CUDA_API_VALIDATION_ERROR:'+str(exc)
  atomic_json(out/'fake_result.json',dict(status='SYNTHETIC_FAILURE',error=error,frames_submitted=0,frames_completed=0,CUDA_context_initialized=torch.cuda.is_initialized(),exception_class=type(exc).__name__,traceback=traceback.format_exc(),error_classification='real Torch CUDA API argument validation; no illegal device access or poisoned context',real_model=False))
  publish_terminal(out,a.session,out/'fake_result.json','cpu_dummy')
  raise SystemExit(2)
finally:
 reporter.finish()
 if guard:guard.finish()
