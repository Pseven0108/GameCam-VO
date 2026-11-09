"""Requests are rejected before real I/O/CUDA/forward; never uses real assets."""
import importlib,pathlib
APIS=['torch.load','torch.serialization.load','safetensors.torch.load_file','safetensors.safe_open','mmengine.runner.load_checkpoint','mmcv.runner.load_checkpoint','torch.hub.load','torch.hub.load_state_dict_from_url','huggingface_hub.hf_hub_download','huggingface_hub.snapshot_download','urllib','requests','socket','cuda','cuda_tensor','model_forward','raw_checkpoint']
def request_forbidden_api(name,torch,guard):
    f='/not-read/cpu-guard-sentinel.pth';url='http://127.0.0.1:9/never-downloaded'
    if name=='torch.load':return torch.load(f)
    if name=='torch.serialization.load':return torch.serialization.load(f)
    if name=='safetensors.torch.load_file':return importlib.import_module('safetensors.torch').load_file('/not-read/cpu-guard.safetensors')
    if name=='safetensors.safe_open':return importlib.import_module('safetensors').safe_open('/not-read/cpu-guard.safetensors',framework='pt')
    if name in ('mmengine.runner.load_checkpoint','mmcv.runner.load_checkpoint'):
        module=importlib.import_module(name.rsplit('.',1)[0]);return module.load_checkpoint(None,f)
    if name=='torch.hub.load':return torch.hub.load('not-a-repo/not-a-repo','not-a-model')
    if name=='torch.hub.load_state_dict_from_url':return torch.hub.load_state_dict_from_url(url)
    if name=='huggingface_hub.hf_hub_download':return importlib.import_module('huggingface_hub').hf_hub_download('not-a-repo/not-a-repo','sentinel.pth')
    if name=='huggingface_hub.snapshot_download':return importlib.import_module('huggingface_hub').snapshot_download('not-a-repo/not-a-repo')
    if name=='urllib':return importlib.import_module('urllib.request').urlopen(url,timeout=.1)
    if name=='requests':return importlib.import_module('requests').get(url,timeout=.1)
    if name=='socket':
        import socket
        return socket.socket().connect(('127.0.0.1',9))
    if name=='cuda':return torch.cuda.init()
    if name=='cuda_tensor':return torch.empty(1,device='cuda')
    if name=='model_forward':return torch.nn.Identity()(torch.empty(1))
    if name=='raw_checkpoint':return pathlib.Path(f).read_bytes()
    raise ValueError('UNKNOWN_SENTINEL:'+name)
