"""Audited Python file boundary. This is not an OS or native-code sandbox."""
import os,pathlib,re,sys
class ModelIOBoundary:
    def __init__(self,read_files,source_files,protected_roots,output_roots,environment_roots=(),ipc_policy=None):
        self.reads={pathlib.Path(p).resolve() for p in list(read_files)+list(source_files)}
        self.protected=[pathlib.Path(p).resolve() for p in protected_roots]
        self.outputs=[pathlib.Path(p).resolve() for p in output_roots]
        self.environments=[pathlib.Path(p).resolve() for p in environment_roots]
        self.ipc=ipc_policy;self.events=[]
        if any(str(p) in ('/','/dev/shm','/dev/shm/gamecam-ipc','/tmp') for p in self.outputs):raise RuntimeError('MODEL_BROAD_OUTPUT_ROOT_FORBIDDEN')
    def check_path(self,path,write=False,operation='open',flags=None):
        lexical=pathlib.Path(os.path.abspath(path))
        if self.ipc is not None and self.ipc.is_ipc_path(lexical):return self.ipc.check_file(lexical,write,operation,flags)
        p=lexical.resolve()
        if any(p.is_relative_to(r) for r in self.outputs):return True
        if write:raise RuntimeError('MODEL_WRITE_OUTSIDE_OWN_OUTPUT:'+str(p))
        if p in self.reads:return True
        if any(p.is_relative_to(r) for r in self.protected):raise RuntimeError('MODEL_UNAPPROVED_PROJECT_READ:'+str(p))
        if any(p.is_relative_to(r) for r in self.environments) and p.suffix.lower() in {'.py','.pyc','.so','.pyd','.dll'}:return True
        if re.search(r'(?i)(^|[_-])(gt|skeleton|state|npc|monster|camera_pose|ground_truth)([_\-.]|$)',p.name):raise RuntimeError('MODEL_ANALYSIS_DATA_FORBIDDEN:'+str(p))
        if any(p.is_relative_to(r) for r in self.environments):return True
        if p.suffix.lower() in {'.png','.jpg','.jpeg','.exr','.npy','.npz','.pt','.pth','.safetensors','.csv','.mp4'}:raise RuntimeError('MODEL_UNAPPROVED_EXTERNAL_DATA_READ:'+str(p))
        return True
    def audit(self,event,args):
        try:
            if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
                mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
                write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
                self.check_path(os.fsdecode(args[0]),write,'open',flags)
            elif event in {'os.mkdir','os.remove','os.rmdir','os.chmod','os.chown'} and args and isinstance(args[0],(str,bytes,os.PathLike)):
                path=os.fsdecode(args[0]);self.check_path(path,True,event)
                if self.ipc is not None and self.ipc.is_ipc_path(path) and event=='os.remove':self.ipc.file_unlinked(path)
            elif event in {'os.rename','os.link'}:
                self.check_path(os.fsdecode(args[0]),True,event);self.check_path(os.fsdecode(args[1]),True,event)
            elif event=='os.symlink':
                src,dst=map(os.fsdecode,args[:2]);self.check_path(dst,True,event)
                target=pathlib.Path(src) if pathlib.Path(src).is_absolute() else pathlib.Path(dst).parent/src
                self.check_path(target,True,event)
            elif event in {'socket.connect','socket.getaddrinfo','socket.sendto'}:
                self.events.append({'event':'network_denied'});raise RuntimeError('MODEL_NETWORK_FORBIDDEN')
        except RuntimeError as exc:
            self.events.append({'event':'denied_open' if event=='open' else 'denied_filesystem_operation','audit_event':event,'reason':str(exc)});raise
    def install(self):sys.addaudithook(self.audit)
