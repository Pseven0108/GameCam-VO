import json,os,pathlib,sys,torch
from torch.utils.tensorboard import SummaryWriter
p=pathlib.Path(sys.argv[1])/"native"
assert os.environ.get("CUDA_VISIBLE_DEVICES")=="" and not torch.cuda.is_initialized()
assert not p.exists()
w=SummaryWriter(str(p))
try:
 assert p.is_dir()
 try:p.mkdir(parents=True,exist_ok=False)
 except FileExistsError:observed="FileExistsError"
 else:raise AssertionError("Expected native lifecycle defect was not reproduced")
finally:w.close()
assert not torch.cuda.is_initialized()
print(json.dumps({"status":"EXPECTED_FAILURE_REPRODUCED","native_stage_succeeded":False,"observed":observed,"SummaryWriter_created_directory":True,"model_loaded":False,"CUDA_initialized":False}))
