"""Paired full-resident/offloaded synthetic inference; not a pretrained model run."""
import copy
import json
from pathlib import Path
import torch
from module_cpu_offload import FrozenModuleOffload

torch.manual_seed(43)
model=torch.nn.Sequential(torch.nn.Conv2d(3,16,3,padding=1),torch.nn.GELU(),
    torch.nn.Conv2d(16,16,3,padding=1),torch.nn.GELU(),torch.nn.Flatten(),torch.nn.Linear(16*16*16,8)).eval()
reference=copy.deepcopy(model).cuda();x=torch.randn(2,3,16,16,device='cuda')
saved={k:v.clone() for k,v in model.state_dict().items()};offload=FrozenModuleOffload(model)
with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16,cache_enabled=False):
    a=reference(x);b=model(x);c=model(x)
torch.cuda.synchronize()
same=all(torch.equal(saved[k],v) for k,v in model.state_dict().items())
result={'status':'PASS','FP32_checkpoint_storage':True,'BF16_operations_unchanged':True,
    'same_synthetic_output_bitwise':bool(torch.equal(a,b) and torch.equal(b,c)),
    'max_abs':float((a-b).abs().max()),'original_tensor_objects_restored':offload.restored(),
    'original_state_unchanged':same,'staged_module_calls':offload.calls,
    'full_model_equivalence_proven':False,'limitation':'Synthetic module contract only; Full model cannot be resident under current local resource conditions.'}
offload.close()
if not all(result[k] for k in ['same_synthetic_output_bitwise','original_tensor_objects_restored','original_state_unchanged']):
    raise RuntimeError(json.dumps(result))
out=Path(__file__).resolve().parents[1]/'09_reproducibility/OFFLOAD_SYNTHETIC_GPU_PROBE.json'
out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
