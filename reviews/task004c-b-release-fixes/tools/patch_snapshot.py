"""Replace only snapshot planning/save seams in the independent candidate."""
import ast,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'candidate/native_control/snapshot.py';s=p.read_text(encoding='utf-8')
start=s.index('def save_state(');end=s.index('\n\ndef read_manifest(',start)
replacement='''def prepare_state(bundle, *, provenance, services=None, floor_bytes=10*1024**3, allowed_prefixes=None, destination_parent=None):
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
'''
s=s[:start]+replacement+s[end:]
s=s.replace('def load_state(path, *, services=None, expected_sha=None, allow_cuda=False):','def load_state(path, *, services=None, expected_sha=None, allow_cuda=False, cpu_storage_factory=None):')
old="""        raw=raw.clone() if s['device']=='cpu' else raw.to(s['device'])
        if s['cpu_shared']:raw.share_memory_()
"""
new="""        if s['device']=='cpu' and s['cpu_shared'] and cpu_storage_factory is not None:
            raw=cpu_storage_factory(sid,raw,s)
            if raw.dtype!=torch.uint8 or raw.device.type!='cpu' or raw.numel()!=s['byte_size'] or not raw.is_shared() or byte_sha(raw)!=s['raw_sha256']:
                raise ControlError('File-backed restore changed storage content or sharing semantics')
        else:
            raw=raw.clone() if s['device']=='cpu' else raw.to(s['device'])
            if s['cpu_shared']:raw.share_memory_()
"""
assert s.count(old)==1;s=s.replace(old,new);ast.parse(s)
p.write_text(s,encoding='utf-8',newline='\n')
print('Candidate snapshot planning and shared-storage restore callback added')
