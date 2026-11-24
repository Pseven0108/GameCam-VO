"""Explicit state tree, tensor-only torch payloads; no whole-object pickle.

CPU implementation tested here. Native CUDA quiescence/rebinding is a separate
integration requirement; save_checkpoint never initializes CUDA itself.
"""
import base64, hashlib, json, math, os, pathlib, re, sys, uuid
import torch
from control_common import ControlError, canonical, digest, file_sha, require_space, exclusive_json
SCHEMA='GAMECAM_EXPLICIT_CHECKPOINT_V1'

def value_sha(t):
    if t.layout!=torch.strided or t.is_quantized or t.is_conj() or t.is_neg():
        raise ControlError('Only ordinary resolved dense strided tensors are supported')
    return hashlib.sha256(t.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()

def _pack(state):
    storages={}; storage_keys={}; tensors={}; tensor_keys={}
    def encode(x):
        if isinstance(x,torch.Tensor):
            if x.layout!=torch.strided or x.is_quantized or x.is_conj() or x.is_neg(): raise ControlError('Unsupported tensor layout/view')
            if id(x) in tensor_keys: return {'$tensor':tensor_keys[id(x)]}
            s=x.untyped_storage(); key=(str(x.device),s._cdata)
            if key not in storage_keys:
                sid='s%06d'%len(storages);storage_keys[key]=sid
                raw=torch.empty(0,dtype=torch.uint8,device=x.device).set_(s,0,(s.nbytes(),),(1,))
                # An owned CPU copy is essential: no live alias may change a sealed file.
                owned=raw.detach().cpu().clone()
                storages[sid]=owned
            sid=storage_keys[key];tid='t%06d'%len(tensors);tensor_keys[id(x)]=tid
            tensors[tid]={'dtype':str(x.dtype),'shape':list(x.shape),'stride':list(x.stride()),'layout':str(x.layout),
                'device':str(x.device),'storage_id':sid,'storage_offset':x.storage_offset(),
                'requires_grad':bool(x.requires_grad),'is_shared':bool(x.is_shared()),'value_sha256':value_sha(x),
                'logical_bytes':x.numel()*x.element_size()}
            return {'$tensor':tid}
        if x is None or type(x) in (str,int,bool):return x
        if type(x) is float:
            return x if math.isfinite(x) else {'$float':repr(x)}
        if isinstance(x,bytes):return {'$bytes':base64.b64encode(x).decode()}
        if isinstance(x,dict):
            if any(not isinstance(k,str) for k in x):raise ControlError('State dictionaries require string keys')
            return {'$dict':[[k,encode(v)] for k,v in x.items()]}
        if isinstance(x,(list,tuple)):return {'$tuple' if isinstance(x,tuple) else '$list':[encode(v) for v in x]}
        raise ControlError('Unregistered state type: '+type(x).__name__)
    tree=encode(state)
    return tree,tensors,storages

def save_checkpoint(state, path, *, provenance, floor_bytes=10*1024**3, free_bytes=None):
    dest=pathlib.Path(path)
    if dest.exists(): raise ControlError('Immutable checkpoint already exists')
    if provenance.get('artifact_kind') not in ('CPU_SYNTHETIC_STATE','NATIVE_C0'):
        raise ControlError('Explicit checkpoint provenance is required')
    if provenance.get('artifact_kind')=='NATIVE_C0':
        # This release cannot certify live DROID object closure or writer barriers.
        raise ControlError('NATIVE_C0_BLOCKED: native capture/resume hooks not validated')
    require_space(dest.parent,0,floor_bytes,free_bytes)
    tree,tensors,storages=_pack(state)
    nbytes=sum(t.numel() for t in storages.values())
    require_space(dest.parent,nbytes+1024*1024,floor_bytes,free_bytes)
    dest.parent.mkdir(parents=True,exist_ok=True)
    staging=dest.parent/('.'+dest.name+'.staging-'+uuid.uuid4().hex)
    staging.mkdir()
    try:
        files={}; storage_meta={}
        for sid,raw in storages.items():
            require_space(dest.parent,raw.numel()+65536,floor_bytes,free_bytes)
            p=staging/(sid+'.pt')
            with p.open('xb') as f:
                torch.save(raw,f);f.flush();os.fsync(f.fileno())
            files[p.name]={'sha256':file_sha(p),'bytes':p.stat().st_size}
            storage_meta[sid]={'file':p.name,'byte_size':raw.numel(),'raw_sha256':hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
                'cpu_shared':any(t['storage_id']==sid and t['device']=='cpu' and t['is_shared'] for t in tensors.values())}
        manifest={'schema':SCHEMA,'provenance':provenance,'endianness':sys.byteorder,
                  'tree':tree,'tensors':tensors,'storages':storage_meta,'files':files}
        manifest['state_sha256']=digest({k:manifest[k] for k in ('tree','tensors','storages','provenance')})
        exclusive_json(staging/'manifest.json',manifest)
        exclusive_json(staging/'COMPLETE.json',{'manifest_sha256':file_sha(staging/'manifest.json')})
        if dest.exists(): raise ControlError('Destination appeared during save')
        os.rename(staging,dest)
        return manifest
    except BaseException as e:
        # Keep partial staging evidence. Never touch an older sealed checkpoint.
        try:exclusive_json(staging/'FAILED.json',{'error':type(e).__name__,'message':str(e)})
        except Exception:pass
        raise

def _manifest(path):
    root=pathlib.Path(path)
    if root.is_symlink():raise ControlError('Linked checkpoint root forbidden')
    for f in ('COMPLETE.json','manifest.json'):
        if not (root/f).is_file() or (root/f).is_symlink():raise ControlError('Unsealed or linked checkpoint')
    complete=json.loads((root/'COMPLETE.json').read_text())
    if file_sha(root/'manifest.json')!=complete['manifest_sha256']:raise ControlError('Manifest SHA mismatch')
    m=json.loads((root/'manifest.json').read_text())
    if m.get('schema')!=SCHEMA or m.get('endianness')!=sys.byteorder:raise ControlError('Checkpoint schema/endianness mismatch')
    if m['state_sha256']!=digest({k:m[k] for k in ('tree','tensors','storages','provenance')}):raise ControlError('State digest mismatch')
    expected={'COMPLETE.json','manifest.json'}|set(m['files'])
    if {p.name for p in root.iterdir()}!=expected:raise ControlError('Unexpected or missing checkpoint members')
    for name,entry in m['files'].items():
        if not re.fullmatch(r's[0-9]{6}\.pt',name):raise ControlError('Unsafe tensor member path')
        p=root/name
        if p.is_symlink() or not p.is_file() or p.stat().st_size!=entry['bytes'] or file_sha(p)!=entry['sha256']:
            raise ControlError('Tensor file SHA/size mismatch: '+name)
    return m

def load_checkpoint(path, *, expected_identity=None):
    root=pathlib.Path(path);m=_manifest(root)
    if expected_identity:
        for k,v in expected_identity.items():
            if m['provenance'].get(k)!=v:raise ControlError('Checkpoint identity mismatch: '+k)
    storages={}
    for sid,s in m['storages'].items():
        if s['file'] not in m['files']:raise ControlError('Unknown storage member')
        raw=torch.load(root/s['file'],map_location='cpu',weights_only=True)
        if not isinstance(raw,torch.Tensor) or raw.dtype!=torch.uint8 or raw.device.type!='cpu' or raw.ndim!=1 or not raw.is_contiguous():raise ControlError('Unsafe storage payload')
        if raw.numel()!=s['byte_size'] or hashlib.sha256(raw.numpy().tobytes()).hexdigest()!=s['raw_sha256']:raise ControlError('Storage bytes mismatch')
        if s.get('cpu_shared'):raw.share_memory_()
        storages[sid]=raw.untyped_storage()
    cache={}
    def decode(x):
        if not isinstance(x,dict):return x
        if '$tensor' in x:
            tid=x['$tensor']
            if tid not in cache:
                t=m['tensors'][tid];dtype=getattr(torch,t['dtype'].removeprefix('torch.'),None)
                if not isinstance(dtype,torch.dtype):raise ControlError('Invalid tensor dtype')
                if t['layout']!='torch.strided' or len(t['shape'])!=len(t['stride']) or any(v<0 for v in t['shape']+t['stride']) or t['storage_offset']<0:raise ControlError('Invalid tensor shape/stride')
                el=torch.empty(0,dtype=dtype).element_size();size=m['storages'][t['storage_id']]['byte_size']
                end=t['storage_offset']+(1+sum((d-1)*s for d,s in zip(t['shape'],t['stride'])) if all(t['shape']) else 0)
                if end*el>size:raise ControlError('Tensor view exceeds original storage')
                value=torch.empty(0,dtype=dtype).set_(storages[t['storage_id']],t['storage_offset'],tuple(t['shape']),tuple(t['stride']))
                value.requires_grad_(t['requires_grad'])
                if value_sha(value)!=t['value_sha256']:raise ControlError('Logical tensor SHA mismatch: '+tid)
                cache[tid]=value
            return cache[tid]
        if '$dict' in x:return {k:decode(v) for k,v in x['$dict']}
        if '$tuple' in x:return tuple(decode(v) for v in x['$tuple'])
        if '$list' in x:return [decode(v) for v in x['$list']]
        if '$bytes' in x:return base64.b64decode(x['$bytes'],validate=True)
        if '$float' in x:return float(x['$float'])
        raise ControlError('Unknown state tree tag')
    return decode(m['tree'])

def validate_checkpoint(path):
    m=_manifest(path);load_checkpoint(path)
    return {'valid':True,'state_sha256':m['state_sha256'],'tensor_count':len(m['tensors']),'storage_count':len(m['storages']),
            'native_runtime_verified':False,'artifact_kind':m['provenance']['artifact_kind']}

def compare_checkpoint_hashes(a,b):
    ma,mb=_manifest(a),_manifest(b)
    return {'same_state':ma['state_sha256']==mb['state_sha256'],'same_files':ma['files']==mb['files'],
            'same_tensor_values':{k:v['value_sha256'] for k,v in ma['tensors'].items()}=={k:v['value_sha256'] for k,v in mb['tensors'].items()}}
