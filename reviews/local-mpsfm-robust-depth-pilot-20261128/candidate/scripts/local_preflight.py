"""Local GPU/resource audit. Never invokes SSH, remote APIs, or environment installers."""
import json,pathlib,shutil,subprocess,sys
from runtime_local import ROOT,TASK,SOURCE,ASSETS,PREVIOUS,sha,write,DATA,CACHE
import torch
import droid_backends
original='de87a5bc8167634b0aa0986fac02782ebcaa5a9a0793ed388562168bfddfe1fc'
backend=pathlib.Path(droid_backends.__file__)
info=dict(python=sys.version,executable=sys.executable,torch=torch.__version__,cuda=torch.version.cuda,
    gpu=torch.cuda.get_device_name(0),capability=list(torch.cuda.get_device_capability(0)),
    gpu_free_total_bytes=list(torch.cuda.mem_get_info()),
    nvidia_smi=subprocess.check_output(['/usr/lib/wsl/lib/nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu','--format=csv'],text=True),
    compute_processes=subprocess.check_output(['/usr/lib/wsl/lib/nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv'],text=True),
    disk_free_bytes=shutil.disk_usage(ROOT).free,source_commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc',
    original_extension=str(backend),original_extension_sha256=sha(backend),remote_connections=0,
    no_driver_or_environment_changes=True,window='Train Day004 RGB1658-1721',
    cached_raw_inputs=str(DATA),cache=str(CACHE),weights_location=str(ASSETS))
if info['original_extension_sha256']!=original:raise RuntimeError('Installed original extension changed')
if info['gpu_free_total_bytes'][0]<5.7*1024**3:raise RuntimeError('Not enough presently free local VRAM; other apps untouched')
if info['disk_free_bytes']<10*1024**3:raise RuntimeError('Local disk safety margin')
if not json.loads((TASK/'reports/SOURCE_AND_ASSET_AUDIT_V2.json').read_text())['export_all_regular_files_match']:
    raise RuntimeError('Frozen source identity failed')
write(TASK/'reports/LOCAL_PREFLIGHT.json',info)
print(json.dumps(info,indent=2))
