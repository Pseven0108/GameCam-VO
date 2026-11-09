"""CPU-only preflight guards. These are installed only in test subprocesses."""
import os,pathlib,sys,time,traceback
class CPUFactoryGuard:
    def __init__(self):
        if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU_PREFLIGHT_DEVICE_MASK_REQUIRED')
        self.events=[];self.raw_asset_denials=[];self.torch=None;self.torch_installed=False
    def deny(self,kind,request=None,error_type=RuntimeError):
        self.events.append(dict(event='CPU_PREFLIGHT_REJECTED',kind=kind,request=str(request)[:800],unix_time=time.time(),stack=traceback.format_stack(limit=14)))
        raise error_type('CPU_PREFLIGHT_'+kind+'_FORBIDDEN')
    def attach_pins(self,pins):
        self.pins=pins
        pins.boundary=lambda loader,original,*a,**kw:self.deny('CHECKPOINT_LOAD',loader)
        pins.gate.cached_call=lambda kind,old,args,kwargs:self.deny('CHECKPOINT_OR_HUB_CALL',kind)
        sys.addaudithook(self.audit)
    def audit(self,event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            p=pathlib.Path(os.fsdecode(args[0]));mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
            if not writing and (p.suffix.lower() in {'.pth','.pt','.ckpt','.safetensors','.bin','.png','.jpg','.jpeg','.exr','.npy','.npz'} or any(x in p.name.lower() for x in ('camera_pose','ground_truth','skeleton'))):
                self.raw_asset_denials.append(str(p));self.deny('RAW_ASSET_READ',p)
        if event in ('socket.connect','socket.getaddrinfo','socket.sendto'):self.deny('NETWORK',event)
        if event=='subprocess.Popen':
            # Matplotlib treats a denied optional fontconfig probe as OSError.
            # No process executes; arbitrary subprocess requests remain fatal.
            argv=args[1] if len(args)>1 else None
            if isinstance(argv,(list,tuple)) and list(argv) in (['fc-list','--help'],['fc-list','--format=%{file}\n']):self.deny('OPTIONAL_FONTCONFIG_PROCESS',argv,FileNotFoundError)
            self.deny('CHILD_PROCESS',args[:2])
        if event=='os.system':self.deny('CHILD_PROCESS',event)
    def install_torch(self,torch):
        if self.torch_installed:return
        assert not torch.cuda.is_initialized();self.torch=torch
        for owner,attr in [(torch.cuda,'init'),(torch.cuda,'_lazy_init'),(torch._C,'_cuda_init'),(torch.Tensor,'cuda'),(torch.nn.Module,'cuda')]:
            setattr(owner,attr,lambda *a,_name=attr,**kw:self.deny('CUDA',_name))
        for owner in (torch.Tensor,torch.nn.Module):
            original=owner.to
            def guarded_to(obj,*args,_original=original,**kw):
                device=kw.get('device',args[0] if args else None)
                if isinstance(device,(str,torch.device,int)) and str(device).split(':')[0]!='cpu':self.deny('NON_CPU_DEVICE',device)
                if isinstance(device,torch.Tensor) and device.device.type!='cpu':self.deny('NON_CPU_DEVICE',device.device)
                return _original(obj,*args,**kw)
            owner.to=guarded_to
        torch.nn.Module.load_state_dict=lambda *a,**kw:self.deny('STATE_DICT_LOAD')
        torch.nn.Module._call_impl=lambda *a,**kw:self.deny('MODEL_FORWARD')
        # safe_open is a native extension entry: guard it explicitly before
        # any factory imports can bind an alias that bypasses Python profiling.
        import importlib
        self.patch_dependency(importlib.import_module('safetensors'))
        self.torch_installed=True
    def profile(self,frame,event,arg):
        if event!='call':return
        name=frame.f_code.co_name;file=frame.f_code.co_filename;loc=frame.f_locals
        if (name in ('load','load_file','safe_open','load_checkpoint','_load_checkpoint','load_state_dict_from_url','download_url_to_file','hf_hub_download','snapshot_download') and any(x in file for x in ('/torch/serialization','/torch/hub','/safetensors','/mmcv/runner','/mmengine/runner','/huggingface_hub'))):self.deny('CHECKPOINT_OR_DOWNLOAD_API',file+':'+name)
        if name=='create_model' and '/timm/' in file and loc.get('pretrained') is not False:self.deny('PRETRAINED_TRUE',dict(factory='timm.create_model',pretrained=loc.get('pretrained')))
        if '/baselines/droid_w/upstream/' in file and name=='__init__' and type(loc.get('self')).__name__ in ('Tracker','DepthVideo','DroidNet'):self.deny('DROID_CONSTRUCTION',name)
    def patch_dependency(self,module):
        if getattr(module,'__name__','')=='safetensors' and hasattr(module,'safe_open'):
            current=module.safe_open
            if getattr(current,'_cpu_factory_guard',None) is self:return
            def rejected(*a,**kw):return self.deny('CHECKPOINT_API','safetensors.safe_open')
            rejected._cpu_factory_guard=self;module.safe_open=rejected
    def snapshot(self):
        return dict(CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),torch_version=self.torch.__version__ if self.torch else None,cuda_context_initialized=bool(self.torch and self.torch.cuda.is_initialized()),events=self.events,raw_asset_denials=self.raw_asset_denials,guard='CPU subprocess only; real RuntimePins bindings retained, callable destinations deny checkpoints')
