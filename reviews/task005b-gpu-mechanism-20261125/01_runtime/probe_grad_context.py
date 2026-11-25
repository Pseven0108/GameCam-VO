import pathlib,json,sys
import torch
hist=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/source_candidate');sys.path.insert(0,str(hist));from checkpoint.rng_state import capture_rng_state
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');m=json.loads((r/'snapshots/D1_S1_RGB019/manifest.json').read_text());nodes=m['nodes']
root=nodes[m['root']['$ref']];rng_ref=dict(root['items'])['rng'];rng=nodes[rng_ref['$ref']];flags=dict(nodes[dict(rng['items'])['flags']['$ref']]['items'])
before=capture_rng_state()['flags']
with torch.no_grad():inside=capture_rng_state()['flags']
result={'saved':flags,'fresh_process':before,'inside_no_grad':inside,'differences_before':{k:[flags[k],before[k]] for k in flags if flags[k]!=before[k]},'no_grad_matches_all_flags':flags==inside,'cuda_context_initialized':torch.cuda.is_initialized(),'model_imported':False,'native_BA_called':False}
print(json.dumps(result))
