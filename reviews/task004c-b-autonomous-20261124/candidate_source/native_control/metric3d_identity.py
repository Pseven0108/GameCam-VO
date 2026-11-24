"""One source-pinned, behavior-pinned inference identity; unknown lambdas fail."""
import dis
import hashlib
import inspect
from pathlib import Path
import types

from control_common import ControlError

TAG='metric3d_lora_identity_callable_v1'
MODULE='mono.model.decode_heads.RAFTDepthNormalDPTDecoder5'
CLASSES=tuple(MODULE+':'+name for name in ('LoRALinear','ConvTranspose2dLoRA','Conv2dLoRA'))
SOURCE_SHA='24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951'
CODE_SHA='8268a0999f621ea90e82f512d702565764559033232c0da218c4f77f1e34d7f3'
PIN={'tag':TAG,'version':1,'module':MODULE,'attribute':'lora_dropout',
     'source_sha256':SOURCE_SHA,'bytecode_sha256':CODE_SHA,'dropout_branch':'p=0; identity',
     'qualname':'LoRALayer.__init__.<locals>.<lambda>','signature':'(x) -> same object'}


class Metric3DLoRAIdentityV1:
    """Top-level construction-free callable. Separate instances preserve memo aliases."""
    __slots__=('owner_class',)
    def __call__(self,x):return x


def check_source(owner_class):
    if owner_class.__module__+':'+owner_class.__qualname__ not in CLASSES:
        raise ControlError('Identity adapter owner class mismatch')
    p=inspect.getsourcefile(owner_class)
    if not p or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=SOURCE_SHA:
        raise ControlError('Identity adapter installed Metric3D source SHA mismatch')


def validate(owner,attr,fn):
    check_source(type(owner))
    if attr!='lora_dropout':raise ControlError('Identity adapter attribute mismatch')
    pin={**PIN,'class':type(owner).__module__+':'+type(owner).__qualname__}
    if isinstance(fn,Metric3DLoRAIdentityV1):
        if fn.owner_class!=pin['class']:raise ControlError('Restored identity owner pin mismatch')
        return pin
    if type(fn) is not types.FunctionType:raise ControlError('Identity adapter needs the audited function')
    c=fn.__code__
    if (fn.__module__!=MODULE or fn.__qualname__!=PIN['qualname'] or fn.__closure__ is not None
        or c.co_freevars or c.co_cellvars or c.co_argcount!=1 or c.co_posonlyargcount!=0
        or c.co_kwonlyargcount!=0 or c.co_flags&0x0c or fn.__defaults__ is not None
        or fn.__kwdefaults__ is not None or fn.__dict__ or c.co_names
        or hashlib.sha256(c.co_code).hexdigest()!=CODE_SHA
        or [(i.opname,i.arg) for i in dis.get_instructions(fn)]!=[('LOAD_FAST',0),('RETURN_VALUE',None)]):
        raise ControlError('Identity adapter function/closure/bytecode mismatch')
    if c.co_filename!=inspect.getsourcefile(type(owner)):
        raise ControlError('Identity adapter callable provenance differs from its owner')
    # Bytecode proves no read/write/call/RNG operation. No probing the live RNG here.
    sentinel=object()
    if fn(sentinel) is not sentinel:raise ControlError('Identity adapter failed strict object identity')
    return pin


def collect(root,services):
    """Pre-index only exact registered owner attributes, before arbitrary ref order."""
    import torch,numpy as np
    seen=set();registered={}
    def visit(x):
        if id(x) in services or x is None or isinstance(x,(str,int,float,bool,bytes,torch.Tensor,
            torch.dtype,torch.device,np.ndarray,np.generic,np.dtype,Path,slice,type)):
            return
        if id(x) in seen:return
        seen.add(id(x))
        if type(x).__module__+':'+type(x).__qualname__ in CLASSES:
            fn=vars(x).get('lora_dropout')
            if isinstance(fn,(types.FunctionType,Metric3DLoRAIdentityV1)):
                pin=validate(x,'lora_dropout',fn)
                if id(fn) in registered and registered[id(fn)]!=pin:
                    raise ControlError('One identity callable has incompatible owner pins')
                registered[id(fn)]=pin
        if isinstance(x,types.MethodType):visit(x.__self__)
        elif isinstance(x,dict):
            for k,v in x.items():visit(k);visit(v)
        elif isinstance(x,(list,tuple,set,frozenset)):
            for v in x:visit(v)
        elif hasattr(x,'__dict__'):
            for v in vars(x).values():visit(v)
    visit(root)
    return registered


def restore(pin):
    if not isinstance(pin,dict) or pin.get('class') not in CLASSES or {k:v for k,v in pin.items() if k!='class'}!=PIN:
        raise ControlError('Unknown identity callable adapter version or signature')
    from importlib import import_module
    check_source(getattr(import_module(MODULE),pin['class'].split(':')[1]))
    value=Metric3DLoRAIdentityV1();value.owner_class=pin['class']
    return value
