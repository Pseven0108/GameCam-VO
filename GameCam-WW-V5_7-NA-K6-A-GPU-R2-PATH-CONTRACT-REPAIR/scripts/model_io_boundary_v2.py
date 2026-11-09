"""Fixed allowlist for model file IO. Defense in depth, not a native-code/OS sandbox."""
import os,pathlib,re,sys
class ModelIOBoundary:
    def __init__(self,read_files,source_files,protected_roots,output_roots,environment_roots=()):
        self.reads={pathlib.Path(p).resolve() for p in list(read_files)+list(source_files)}
        self.protected=[pathlib.Path(p).resolve() for p in protected_roots]
        self.outputs=[pathlib.Path(p).resolve() for p in output_roots]
        self.environments=[pathlib.Path(p).resolve() for p in environment_roots]
        self.events=[]
    def check_path(self,path,write=False):
        p=pathlib.Path(path).resolve()
        if any(p.is_relative_to(r) for r in self.outputs):return True
        if write:raise RuntimeError('MODEL_WRITE_OUTSIDE_OWN_OUTPUT:'+str(p))
        if p in self.reads:return True
        if any(p.is_relative_to(r) for r in self.protected):raise RuntimeError('MODEL_UNAPPROVED_PROJECT_READ:'+str(p))
        # Framework modules such as torch.jit._state are trusted code, not dataset State.
        if any(p.is_relative_to(r) for r in self.environments) and p.suffix.lower() in {'.py','.pyc','.so','.pyd','.dll'}:return True
        if re.search(r'(?i)(^|[_-])(gt|skeleton|state|npc|monster|camera_pose|ground_truth)([_\-.]|$)',p.name):raise RuntimeError('MODEL_ANALYSIS_DATA_FORBIDDEN:'+str(p))
        if any(p.is_relative_to(r) for r in self.environments):return True
        if p.suffix.lower() in {'.png','.jpg','.jpeg','.exr','.npy','.npz','.pt','.pth','.safetensors','.csv','.mp4'}:raise RuntimeError('MODEL_UNAPPROVED_EXTERNAL_DATA_READ:'+str(p))
        # Shared libraries, /proc telemetry, and stdlib are outside project data roots.
        return True
    def audit(self,event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
            write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
            try:self.check_path(os.fsdecode(args[0]),write)
            except RuntimeError as e:self.events.append({'event':'denied_open','reason':str(e)});raise
        if event in {'socket.connect','socket.getaddrinfo','socket.sendto'}:
            self.events.append({'event':'network_denied'});raise RuntimeError('MODEL_NETWORK_FORBIDDEN')
    def install(self):sys.addaudithook(self.audit)
