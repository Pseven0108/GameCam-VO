"""Explicit object graph and tensor-storage snapshot; never pickle live objects.

CPU fixtures verify the format. A native C0 additionally requires the audited
Tracker frame barrier, a source lock, and a successful native closure audit.
"""
import base64
from collections import OrderedDict
import hashlib
import importlib
import inspect
import functools
import json
import math
import os
from pathlib import Path
import sys
import types
import uuid

import numpy as np
import torch

from control_common import ControlError, canonical, digest, file_sha, require_space
from checkpoint.checkpoint_adapter import value_sha

FORMAT = 'GAMECAM_NATIVE_EXPLICIT_OBJECT_STORAGE_V2'
HOOKS = ('_backward_hooks', '_backward_pre_hooks', '_forward_hooks', '_forward_pre_hooks',
         '_state_dict_hooks', '_state_dict_pre_hooks', '_load_state_dict_pre_hooks',
         '_load_state_dict_post_hooks')


def byte_sha(raw):
    view = memoryview(raw.detach().cpu().contiguous().numpy()).cast('B')
    h = hashlib.sha256()
    for pos in range(0, len(view), 8*1024**2):
        h.update(view[pos:pos+8*1024**2])
    return h.hexdigest()


def class_pin(cls):
    if '<locals>' in cls.__qualname__:
        raise ControlError('Local/anonymous classes cannot be restored')
    key = cls.__module__ + ':' + cls.__qualname__
    try:
        source = inspect.getsourcefile(cls)
    except (TypeError, OSError):
        source = None
    return {'key':key, 'source_sha256':file_sha(source) if source and Path(source).is_file() else None}


class ObjectEncoder:
    """All fields are captured, or the whole save fails. Services are explicit."""
    def __init__(self, *, services=None, allowed_prefixes=('src.', 'torch.nn.', 'torchvision.', 'thirdparty.', 'timm.', 'mono.', 'mmcv.', 'mmengine.', 'munch', 'omegaconf.', 'native_control.', 'task003_observer')):
        self.services={id(v):k for k,v in (services or {}).items() if v is not None}
        self.allowed_prefixes=allowed_prefixes
        self.nodes={}; self.memo={}; self.storages={}; self.storage_memo={}; self.classes={}
        self.registered_callables=None

    def encode(self, x):
        from native_control.metric3d_identity import collect, TAG
        if self.registered_callables is None:
            self.registered_callables=collect(x,self.services)
        if id(x) in self.registered_callables:
            if id(x) in self.memo:return {'$ref':self.memo[id(x)]}
            nid='o%07d'%len(self.nodes);self.memo[id(x)]=nid
            self.nodes[nid]={'kind':TAG,'pin':self.registered_callables[id(x)]}
            return {'$ref':nid}
        if x is None or type(x) in (str, int, bool): return x
        if type(x) is float:
            return x if math.isfinite(x) else {'$float':repr(x)}
        if id(x) in self.services: return {'$service':self.services[id(x)]}
        if isinstance(x, bytes): return {'$bytes':base64.b64encode(x).decode()}
        if isinstance(x, torch.dtype): return {'$dtype':str(x)}
        if isinstance(x, torch.device): return {'$device':str(x)}
        if isinstance(x, slice): return {'$slice':[x.start,x.stop,x.step]}
        if isinstance(x, Path): return {'$path':str(x)}
        if isinstance(x, np.generic): return {'$numpy_scalar':[x.dtype.str,base64.b64encode(x.tobytes()).decode()]}
        if isinstance(x, np.dtype): return {'$numpy_dtype':x.str}
        if isinstance(x,type):
            pin=class_pin(x)
            if not any(x.__module__.startswith(p) for p in self.allowed_prefixes):raise ControlError('Unregistered class symbol')
            self.classes[pin['key']]=pin
            return {'$class':pin['key']}
        if isinstance(x, types.MethodType):
            if not x.__func__.__name__.isidentifier(): raise ControlError('Unsafe method reference')
            return {'$method':[self.encode(x.__self__),x.__func__.__name__]}
        if isinstance(x, (types.FunctionType, types.BuiltinFunctionType)):
            module, name = getattr(x,'__module__',None),getattr(x,'__qualname__',None)
            if not module or not name or '<' in name or x is not _resolve(module+':'+name):
                raise ControlError('Unregistered closure/function')
            return {'$function':module+':'+name}
        if id(x) in self.memo: return {'$ref':self.memo[id(x)]}
        nid='o%07d'%len(self.nodes);self.memo[id(x)]=nid;self.nodes[nid]={}
        if isinstance(x, torch.Tensor):
            if x.layout!=torch.strided or x.is_quantized or x.is_conj() or x.is_neg():
                raise ControlError('Unsupported native tensor layout')
            if x.is_leaf and x.grad is not None:raise ControlError('Nonempty tensor gradient requires an explicit training-state adapter')
            s=x.untyped_storage();key=(str(x.device),s._cdata)
            if key not in self.storage_memo:
                sid='s%07d'%len(self.storages);self.storage_memo[key]=sid
                raw=torch.empty(0,dtype=torch.uint8,device=x.device).set_(s,0,(s.nbytes(),),(1,))
                self.storages[sid]={'raw':raw,'device':str(x.device),'shared':x.device.type=='cpu' and x.is_shared()}
            sid=self.storage_memo[key]
            self.storages[sid]['shared'] |= x.device.type=='cpu' and x.is_shared()
            node={'kind':'tensor','storage':sid,'dtype':str(x.dtype),'device':str(x.device),
                  'shape':list(x.shape),'stride':list(x.stride()),'offset':x.storage_offset(),
                  'parameter':isinstance(x,torch.nn.Parameter),'requires_grad':x.requires_grad,'sha256':value_sha(x)}
        elif isinstance(x, torch.Generator):
            node={'kind':'generator','device':str(x.device),'state':self.encode(x.get_state())}
        elif isinstance(x, np.ndarray):
            if x.dtype.hasobject: raise ControlError('Object numpy arrays forbidden')
            # Native runtime ndarray caches are value-preserved; shared ndarray views
            # require an explicit adapter and are deliberately rejected below.
            if x.base is not None: raise ControlError('Numpy alias/view needs registered adapter')
            node={'kind':'ndarray','dtype':x.dtype.str,'shape':list(x.shape),'data':self.encode(torch.from_numpy(x.copy()))}
        elif isinstance(x,functools.partial):
            node={'kind':'partial','function':self.encode(x.func),'args':self.encode(x.args),'keywords':self.encode(x.keywords),'attrs':self.encode(vars(x))}
        elif type(x) in (dict,OrderedDict):
            node={'kind':'ordered_dict' if type(x) is OrderedDict else 'dict','items':[[self.encode(k),self.encode(v)] for k,v in x.items()]}
        elif type(x) in (list,tuple,set,frozenset,torch.Size):
            kind={list:'list',tuple:'tuple',set:'set',frozenset:'frozenset',torch.Size:'torch_size'}[type(x)]
            values=sorted(x,key=repr) if type(x) in (set,frozenset) else x
            node={'kind':kind,'items':[self.encode(v) for v in values]}
        elif hasattr(x,'__dict__'):
            cls=type(x); pin=class_pin(cls)
            if not any(cls.__module__.startswith(p) for p in self.allowed_prefixes):
                raise ControlError('Unregistered native object class: '+pin['key'])
            if isinstance(x,torch.nn.Module):
                for name in HOOKS:
                    if getattr(x,name,{}):raise ControlError('Nonempty model hook registry: '+pin['key']+'.'+name)
                if cls.get_extra_state is not torch.nn.Module.get_extra_state:
                    raise ControlError('Custom model extra_state needs explicit adapter: '+pin['key'])
            self.classes[pin['key']]=pin
            attrs=[]
            for k,v in vars(x).items():
                try:attrs.append([k,self.encode(v)])
                except ControlError as e:raise ControlError(pin['key']+'.'+k+': '+str(e)) from e
            node={'kind':'object','class':pin['key'],'attrs':attrs}
        else:
            raise ControlError('Unsupported live runtime field type: '+repr(type(x)))
        self.nodes[nid]=node
        return {'$ref':nid}


def _resolve(key):
    module,name=key.split(':',1); obj=importlib.import_module(module)
    for part in name.split('.'):
        if not part.isidentifier(): raise ControlError('Unsafe qualified name')
        obj=getattr(obj,part)
    return obj


def prepare_state(bundle, *, provenance, services=None, floor_bytes=10*1024**3, allowed_prefixes=None, destination_parent=None):
    import copy
    from native_control.storage_budget import CountingHashWriter,make_budget,block_size
    if provenance.get('artifact_kind') not in ('CPU_NATIVE_INTERFACE_FIXTURE','NATIVE_C0'):
        raise ControlError('Missing snapshot provenance')
    if provenance['artifact_kind']=='NATIVE_C0' and not provenance.get('writer_barrier_and_closure_passed'):
        raise ControlError('NATIVE_C0 requires live writer barrier and closure audit')
    if torch.cuda.is_initialized():torch.cuda.synchronize()
    encoder=ObjectEncoder(services=services,**({'allowed_prefixes':allowed_prefixes} if allowed_prefixes else {}))
    tree=encoder.encode(bundle);files={};storage_meta={}
    for sid,record in encoder.storages.items():
        raw=record['raw'].detach().cpu().clone()
        count=CountingHashWriter();torch.save(raw,count)
        name=sid+'.pt'
        files[name]={'sha256':count.hash.hexdigest(),'bytes':count.bytes}
        storage_meta[sid]={'file':name,'byte_size':raw.numel(),'raw_sha256':byte_sha(raw),
                           'device':record['device'],'cpu_shared':record['shared']}
        del raw
    manifest={'schema':FORMAT,'provenance':copy.deepcopy(provenance),'endianness':sys.byteorder,
              'root':tree,'nodes':encoder.nodes,'classes':encoder.classes,'storages':storage_meta,'files':files}
    manifest['state_sha256']=digest(manifest)
    manifest_raw=canonical(manifest)
    complete_raw=canonical({'manifest_sha256':hashlib.sha256(manifest_raw).hexdigest()})
    budget=make_budget(files,len(manifest_raw),len(complete_raw),
                       block_size=block_size(destination_parent) if destination_parent is not None else 4096,
                       floor_bytes=floor_bytes)
    budget['unique_runtime_storage_bytes']=sum(x['byte_size'] for x in storage_meta.values())
    return {'encoder':encoder,'manifest':manifest,'manifest_raw':manifest_raw,'complete_raw':complete_raw,'budget':budget}


def save_prepared_state(prepared,path):
    from native_control.storage_budget import check_budget
    dest=Path(path)
    if dest.exists():raise ControlError('Immutable native checkpoint already exists')
    m=prepared['manifest'];budget=prepared['budget']
    if canonical(m)!=prepared['manifest_raw'] or digest({k:v for k,v in m.items() if k!='state_sha256'})!=m['state_sha256']:
        raise ControlError('Prepared checkpoint plan was modified')
    # Keep the legacy require_space seam as well as the exact remaining-file guard.
    require_space(dest.parent,budget['minimum_free_before_save_bytes']-budget['safety_floor_bytes'],budget['safety_floor_bytes'])
    check_budget(dest.parent,budget)
    remaining=[x['bytes'] for x in m['files'].values()]+[len(prepared['manifest_raw']),len(prepared['complete_raw'])]
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=dest.parent/('.'+dest.name+'.staging-'+uuid.uuid4().hex);stage.mkdir()
    try:
        for sid,record in prepared['encoder'].storages.items():
            meta=m['storages'][sid];expected=m['files'][meta['file']]
            raw=record['raw'].detach().cpu().clone()
            if byte_sha(raw)!=meta['raw_sha256']:raise ControlError('Runtime storage changed after exact budget planning: '+sid)
            check_budget(dest.parent,budget,remaining_files=remaining)
            file=stage/meta['file']
            with file.open('xb') as f:
                os.posix_fallocate(f.fileno(),0,expected['bytes'])
                torch.save(raw,f);f.flush();os.fsync(f.fileno())
            if file.stat().st_size!=expected['bytes'] or file_sha(file)!=expected['sha256']:
                raise ControlError('Actual tensor archive does not match exact size/SHA plan')
            remaining.pop(0);del raw
        for name,raw in [('manifest.json',prepared['manifest_raw']),('COMPLETE.json',prepared['complete_raw'])]:
            check_budget(dest.parent,budget,remaining_files=remaining)
            with (stage/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            remaining.pop(0)
        check_budget(dest.parent,budget,remaining_files=[])
        if dest.exists():raise ControlError('Checkpoint destination appeared during capture')
        os.rename(stage,dest)
        return m
    except BaseException as e:
        with (stage/'FAILED.json').open('x') as f:json.dump({'error':type(e).__name__,'reason':str(e),'storage_budget':budget},f)
        raise


def save_state(bundle,path,*,provenance,services=None,floor_bytes=10*1024**3,allowed_prefixes=None):
    if Path(path).exists():raise ControlError('Immutable native checkpoint already exists')
    prepared=prepare_state(bundle,provenance=provenance,services=services,floor_bytes=floor_bytes,
                           allowed_prefixes=allowed_prefixes,destination_parent=Path(path).parent)
    return save_prepared_state(prepared,path)


def read_manifest(path, expected_sha=None):
    p=Path(path)
    if p.is_symlink():raise ControlError('Linked checkpoint root')
    for n in ('manifest.json','COMPLETE.json'):
        if (p/n).is_symlink() or not (p/n).is_file():raise ControlError('Unsealed checkpoint')
    m=json.loads((p/'manifest.json').read_bytes());complete=json.loads((p/'COMPLETE.json').read_bytes())
    if file_sha(p/'manifest.json')!=complete['manifest_sha256']:raise ControlError('Manifest SHA mismatch')
    if m['schema']!=FORMAT or m['endianness']!=sys.byteorder:raise ControlError('Native snapshot format mismatch')
    if digest({k:v for k,v in m.items() if k!='state_sha256'})!=m['state_sha256']:raise ControlError('Native snapshot state digest mismatch')
    if expected_sha and m['state_sha256']!=expected_sha:raise ControlError('Unexpected C0 identity')
    if {x.name for x in p.iterdir()}!=set(m['files'])|{'manifest.json','COMPLETE.json'}:raise ControlError('Unexpected snapshot member')
    for name,entry in m['files'].items():
        if Path(name).name!=name or not name.startswith('s') or not name.endswith('.pt'):raise ControlError('Unsafe tensor path')
        q=p/name
        if q.is_symlink() or q.stat().st_size!=entry['bytes'] or file_sha(q)!=entry['sha256']:raise ControlError('Storage SHA mismatch: '+name)
    return m


def load_state(path, *, services=None, expected_sha=None, allow_cuda=False, cpu_storage_factory=None):
    root=Path(path);m=read_manifest(root,expected_sha)
    if any(s['device'].startswith('cuda') for s in m['storages'].values()):
        if not allow_cuda or not torch.cuda.is_initialized():
            raise ControlError('Explicitly admitted, already initialized CUDA process required')
    classes={}
    for key,pin in m['classes'].items():
        cls=_resolve(key)
        if class_pin(cls)!=pin:raise ControlError('Runtime class implementation SHA mismatch: '+key)
        classes[key]=cls
    # Validate every file before deserializing tensor-only payloads.
    storages={}
    for sid,s in m['storages'].items():
        raw=torch.load(str(root/s['file']),map_location='cpu',weights_only=True,mmap=True)
        if not isinstance(raw,torch.Tensor) or raw.dtype!=torch.uint8 or raw.ndim!=1 or not raw.is_contiguous() or raw.numel()!=s['byte_size'] or byte_sha(raw)!=s['raw_sha256']:
            raise ControlError('Invalid tensor-only storage payload')
        # Each original storage is moved once. Per-view .to() would break aliasing.
        if s['device']=='cpu' and s['cpu_shared'] and cpu_storage_factory is not None:
            raw=cpu_storage_factory(sid,raw,s)
            if raw.dtype!=torch.uint8 or raw.device.type!='cpu' or raw.numel()!=s['byte_size'] or not raw.is_shared() or byte_sha(raw)!=s['raw_sha256']:
                raise ControlError('File-backed restore changed storage content or sharing semantics')
        else:
            raw=raw.clone() if s['device']=='cpu' else raw.to(s['device'])
            if s['cpu_shared']:raw.share_memory_()
        storages[sid]=raw.untyped_storage()
    objects={}; constructing=set();services=services or {}
    def decode(x):
        if not isinstance(x,dict):return x
        if '$service' in x:
            if x['$service'] not in services:raise ControlError('Required runtime service not rebound: '+x['$service'])
            return services[x['$service']]
        if '$float' in x:return float(x['$float'])
        if '$bytes' in x:return base64.b64decode(x['$bytes'],validate=True)
        if '$dtype' in x:return getattr(torch,x['$dtype'].removeprefix('torch.'))
        if '$device' in x:return torch.device(x['$device'])
        if '$path' in x:return Path(x['$path'])
        if '$slice' in x:return slice(*x['$slice'])
        if '$numpy_dtype' in x:return np.dtype(x['$numpy_dtype'])
        if '$numpy_scalar' in x:return np.frombuffer(base64.b64decode(x['$numpy_scalar'][1]),dtype=x['$numpy_scalar'][0])[0]
        if '$class' in x:return classes[x['$class']]
        if '$function' in x:return _resolve(x['$function'])
        if '$method' in x:return getattr(decode(x['$method'][0]),x['$method'][1])
        if set(x)!={'$ref'}:raise ControlError('Unknown object graph tag')
        nid=x['$ref']
        if nid in objects:return objects[nid]
        if nid in constructing:raise ControlError('Unsupported cycle through immutable object')
        constructing.add(nid);n=m['nodes'][nid];kind=n['kind']
        if kind=='tensor':
            s=m['storages'][n['storage']];dtype=getattr(torch,n['dtype'].removeprefix('torch.'))
            if not isinstance(dtype,torch.dtype) or len(n['shape'])!=len(n['stride']) or n['offset']<0 or any(v<0 for v in n['shape']+n['stride']):raise ControlError('Invalid native tensor view')
            last=n['offset']+(1+sum((d-1)*v for d,v in zip(n['shape'],n['stride'])) if all(n['shape']) else 0)
            if last*torch.empty(0,dtype=dtype).element_size()>s['byte_size']:raise ControlError('Tensor view exceeds captured storage')
            value=torch.empty(0,dtype=dtype,device=s['device']).set_(storages[n['storage']],n['offset'],tuple(n['shape']),tuple(n['stride']))
            if n['parameter']:value=torch.nn.Parameter(value,requires_grad=n['requires_grad'])
            else:value.requires_grad_(n['requires_grad'])
            if value_sha(value)!=n['sha256']:raise ControlError('Restored tensor SHA mismatch: '+nid)
        elif kind in ('dict','ordered_dict'):
            value={} if kind=='dict' else OrderedDict();objects[nid]=value
            for k,v in n['items']:value[decode(k)]=decode(v)
        elif kind in ('list','set'):
            value=[] if kind=='list' else set();objects[nid]=value
            for v in n['items']:(value.append if kind=='list' else value.add)(decode(v))
        elif kind in ('tuple','frozenset','torch_size'):
            ctor={'tuple':tuple,'frozenset':frozenset,'torch_size':torch.Size}[kind]
            value=ctor(decode(v) for v in n['items'])
        elif kind=='generator':
            if n['device'].startswith('cuda') and not allow_cuda:raise ControlError('CUDA generator not admitted')
            value=torch.Generator(device=n['device']);value.set_state(decode(n['state']))
        elif kind=='partial':
            value=functools.partial(decode(n['function']),*decode(n['args']),**decode(n['keywords']));value.__dict__.update(decode(n['attrs']))
        elif kind=='ndarray':value=decode(n['data']).numpy().astype(n['dtype'],copy=True).reshape(n['shape'])
        elif kind=='metric3d_lora_identity_callable_v1':
            from native_control.metric3d_identity import restore
            value=restore(n['pin'])
        elif kind=='object':
            cls=classes[n['class']]
            # No model constructors, checkpoint loaders, or RNG draws during restore.
            try:value=object.__new__(cls)
            except TypeError as e:raise ControlError('Class needs an explicit construction-free adapter: '+n['class']) from e
            objects[nid]=value
            for key,val in n['attrs']:object.__setattr__(value,key,decode(val))
        else:raise ControlError('Unknown snapshot node type: '+kind)
        objects[nid]=value;constructing.remove(nid)
        return value
    result=decode(m['root'])
    if torch.cuda.is_initialized():torch.cuda.synchronize()
    return result,m


def state_inventory(bundle, *, services=None, allowed_prefixes=None):
    enc=ObjectEncoder(services=services,**({'allowed_prefixes':allowed_prefixes} if allowed_prefixes else {}));enc.encode(bundle)
    return {'object_nodes':len(enc.nodes),'tensor_nodes':sum(v['kind']=='tensor' for v in enc.nodes.values()),
            'storage_bytes':sum(s['raw'].numel() for s in enc.storages.values()),
            'cpu_shared_storage_bytes':sum(s['raw'].numel() for s in enc.storages.values() if s['shared']),
            'class_pins':enc.classes,'node_inventory':{k:{a:b for a,b in v.items() if a not in ('attrs','items')} for k,v in enc.nodes.items()}}
