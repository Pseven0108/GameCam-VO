"""Defense-in-depth model data boundary. Not an OS sandbox; fixed audited call graph is also required."""
import os,pathlib,sys
from launch_contract import ROOT,AUDIT,PREFLIGHT,REFERENCE,mapped
class ModelIOBoundary:
    def __init__(self,spec,case,output,session_dir):
        self.output=pathlib.Path(output).resolve();self.session=pathlib.Path(session_dir).resolve();self.events=[]
        self.reads={mapped(r['path_linux']).resolve() for r in spec['weights']}
        self.reads.update(mapped(r['real_linux']).resolve() for r in spec['weights'])
        self.reads.update(mapped(r['path_linux']).resolve() for r in case['frames'])
        self.reads.update((REFERENCE/r['path']).resolve() for r in spec['files'].values())
        self.reads.update([mapped(spec['config']['path_linux']).resolve(),mapped(spec['k4_live_contract']['path_linux']).resolve(),mapped(spec['hf']['ref_path_linux']).resolve(),(REFERENCE/'config/dependency_pins.json').resolve(),(PREFLIGHT/'GPU_09_120frame_effective_config.json').resolve()])
    def check_path(self,path,write=False):
        p=pathlib.Path(path).resolve()
        if p.is_relative_to(self.output) or p.is_relative_to(self.session):return True
        if write:
            if p.is_relative_to(ROOT.parent) or p.is_relative_to(ROOT):raise RuntimeError('MODEL_WRITE_OUTSIDE_OWN_OUTPUT:'+str(p))
            return True
        if p in self.reads or p.is_relative_to(AUDIT):return True
        if p.is_relative_to(ROOT/'baselines') and p.suffix in {'.py','.pyc','.so','.json','.yaml','.yml','.md','.txt','.csv','.cfg','.ini'}:return True
        if p.is_relative_to(ROOT/'data/sota_assets/DROID_W') and p.suffix=='.json':return True
        if p.is_relative_to(ROOT.parent):raise RuntimeError('MODEL_UNAPPROVED_PROJECT_DATA_READ:'+str(p))
        if p.is_relative_to(pathlib.Path('/opt/gamecam/envs/droidw-cu126')):return True
        if p.suffix.lower() in {'.png','.jpg','.jpeg','.exr','.npy','.npz','.pth','.pt','.safetensors'}:raise RuntimeError('MODEL_UNAPPROVED_EXTERNAL_DATA_READ:'+str(p))
        return True
    def audit(self,event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
            writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
            try:self.check_path(os.fsdecode(args[0]),writing)
            except RuntimeError as exc:self.events.append({'event':'denied_open','reason':str(exc)});raise
        if event in {'socket.connect','socket.getaddrinfo'}:self.events.append({'event':'network_denied'});raise RuntimeError('MODEL_NETWORK_FORBIDDEN')
    def install(self):sys.addaudithook(self.audit)