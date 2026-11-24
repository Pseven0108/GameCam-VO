"""Owned MAP_SHARED CPU storages with explicit spawn reconstruction by path.

Only registered storages use this reducer. Unregistered CPU storage and CUDA
Tensor reduction retain the installed Torch implementation.
"""
from multiprocessing.reduction import ForkingPickler
import math,os,pathlib,stat,uuid
import torch
import torch.multiprocessing.reductions as reductions
from control_common import ControlError,require_space

SCHEMA='GAMECAM_OWNED_FILE_STORAGE_V1'
_original_reducer=reductions.reduce_storage
_installed=False
_owned={}
_cache={}
_arenas={}
_FIELDS={'schema','root','path','byte_size','st_dev','st_ino','mode'}

def install_reducer():
    global _installed
    if not _installed:
        ForkingPickler.register(torch.UntypedStorage,reduce_owned_storage)
        _installed=True

def descriptor_for(storage):
    entry=_owned.get(int(storage._cdata))
    return dict(entry['descriptor']) if entry is not None else None

def validate_descriptor(desc):
    if type(desc) is not dict or set(desc)!=_FIELDS or desc['schema']!=SCHEMA:
        raise ControlError('Invalid file-backed storage descriptor')
    root,path=pathlib.Path(desc['root']),pathlib.Path(desc['path'])
    if not root.is_absolute() or not path.is_absolute() or root.is_symlink() or path.is_symlink():
        raise ControlError('File storage requires an absolute, unlinked owned path')
    if path.resolve().parent!=root.resolve() or path.name!=str(desc['st_ino'])+'.bin':
        raise ControlError('File storage path escaped its namespace or identity')
    if type(desc['byte_size']) is not int or desc['byte_size']<=0:raise ControlError('Invalid file storage byte count')
    s=path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_dev!=desc['st_dev'] or s.st_ino!=desc['st_ino'] or s.st_size!=desc['byte_size']:
        raise ControlError('Backing file identity or byte length changed')
    if stat.S_IMODE(s.st_mode)!=desc['mode'] or desc['mode']!=0o600:
        raise ControlError('Backing file permissions changed')
    return path

def rebuild_owned_storage(desc):
    path=validate_descriptor(desc);key=(os.getpid(),desc['st_dev'],desc['st_ino'],desc['byte_size'])
    if key not in _cache:
        raw=torch.from_file(str(path),shared=True,size=desc['byte_size'],dtype=torch.uint8)
        if not raw.is_shared() or raw.untyped_storage().nbytes()!=desc['byte_size']:
            raise ControlError('Installed Torch did not provide the requested shared file storage')
        _cache[key]=raw
        _owned[int(raw.untyped_storage()._cdata)]={'descriptor':dict(desc),'raw':raw}
    install_reducer()
    return _cache[key].untyped_storage()

def reduce_owned_storage(storage):
    desc=descriptor_for(storage)
    if desc is None:return _original_reducer(storage)
    if storage.device.type!='cpu' or storage.nbytes()!=desc['byte_size']:
        raise ControlError('Registered file storage device/size mismatch')
    validate_descriptor(desc)
    return rebuild_owned_storage,(desc,)

class FileArena:
    def __init__(self,root,*,floor_bytes=10*1024**3):
        self.root=pathlib.Path(root)
        if not self.root.is_absolute():raise ControlError('File arena root must be absolute')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=False)
        if self.root.resolve()!=self.root or self.root.is_symlink():raise ControlError('Linked file arena root')
        self.floor_bytes=floor_bytes;self.descriptors=[]
        install_reducer()

    def raw_storage(self,byte_size):
        if type(byte_size) is not int or byte_size<=0:raise ControlError('File storage must have a positive byte length')
        require_space(self.root,byte_size+65536,self.floor_bytes)
        temp=self.root/('.allocate-'+uuid.uuid4().hex)
        fd=os.open(temp,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        try:
            # Real disk reservation: a sparse logical file alone is not capacity proof.
            os.posix_fallocate(fd,0,byte_size);s=os.fstat(fd);os.fsync(fd)
            path=self.root/(str(s.st_ino)+'.bin')
            os.rename(temp,path)
        finally:os.close(fd)
        desc={'schema':SCHEMA,'root':str(self.root),'path':str(path),'byte_size':byte_size,
              'st_dev':s.st_dev,'st_ino':s.st_ino,'mode':0o600}
        storage=rebuild_owned_storage(desc);self.descriptors.append(desc)
        return torch.empty(0,dtype=torch.uint8).set_(storage,0,(byte_size,),(1,))

    def zeros(self,shape,*,dtype=torch.float32):
        shape=tuple(shape)
        if any(type(x) is not int or x<0 for x in shape):raise ControlError('Invalid mapped tensor shape')
        elements=math.prod(shape);el=torch.empty(0,dtype=dtype).element_size()
        if elements==0:return torch.zeros(shape,dtype=dtype)
        raw=self.raw_storage(elements*el)
        value=torch.empty(0,dtype=dtype).set_(raw.untyped_storage(),0,shape)
        value.zero_()
        return value

    def restore_storage(self,sid,raw,metadata):
        if raw.device.type!='cpu' or raw.dtype!=torch.uint8 or raw.ndim!=1 or raw.numel()!=metadata['byte_size']:
            raise ControlError('Invalid CPU restore storage request')
        if raw.numel()==0:
            value=raw.clone()
            if metadata.get('cpu_shared'):value.share_memory_()
            return value
        value=self.raw_storage(raw.numel());value.copy_(raw)
        return value

def cpu_zeros(name,shape,*,dtype,native_share=False):
    """Allocation-only seam; no optimization values or formulas are altered."""
    root=os.environ.get('GAMECAM_FILE_BACKED_CPU_ROOT')
    if not root:
        tensor=torch.zeros(shape,dtype=dtype,device='cpu')
        return tensor.share_memory_() if native_share else tensor
    key=(os.getpid(),root)
    if key not in _arenas:_arenas[key]=FileArena(pathlib.Path(root))
    return _arenas[key].zeros(shape,dtype=dtype)

def mapped_storage_summary():
    entries=[dict(x['descriptor']) for x in _owned.values()]
    return {'schema':SCHEMA,'storages':entries,'registered_bytes':sum(x['byte_size'] for x in entries),
            'reducer_installed':_installed,'pid':os.getpid()}
