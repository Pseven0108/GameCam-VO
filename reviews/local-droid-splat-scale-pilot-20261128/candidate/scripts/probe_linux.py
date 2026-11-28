"""Read-only probe using the already installed WSL environment."""
import hashlib, importlib.util, json, os, pathlib, shutil, sys
ENV = pathlib.Path('/home/lsuser/.local/share/gamecam-vo/envs/droid-w')
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, '/mnt/d/aaa/GameCam-VO/baselines/droid_w/upstream')
import torch
import droid_backends
import lietorch
import torch_scatter

def digest(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()

result = dict(python=sys.version, torch=torch.__version__, cuda=torch.version.cuda,
    cuda_available=torch.cuda.is_available(), backend=droid_backends.__file__,
    backend_sha256=digest(droid_backends.__file__), gpu=torch.cuda.get_device_name(0),
    compute_capability=torch.cuda.get_device_capability(0), free_total=torch.cuda.mem_get_info(),
    nvcc=str(ENV/'bin/nvcc'), nvcc_exists=(ENV/'bin/nvcc').exists(),
    disk=shutil.disk_usage(ROOT)._asdict(), modules={})
for m in ['src.depth_video','src.frontend','src.tracker','src.slam',
          'src.utils.mono_priors.metric_depth_estimators', 'src.utils.mono_priors.img_feature_extractors']:
    try:
        __import__(m)
        result['modules'][m]='PASS'
    except Exception as e:
        result['modules'][m]=f'{type(e).__name__}: {e}'
dest=ROOT/'candidate/reports/LOCAL_LINUX_PROBE.json'
dest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
