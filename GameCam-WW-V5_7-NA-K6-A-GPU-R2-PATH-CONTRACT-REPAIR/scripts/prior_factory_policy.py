"""Validate the optional exact config dependency repair, bound to candidate SHA."""
import ast,hashlib,json,pathlib
from runtime_dependency_pins import require
SCHEMA='gamecam-prior-factory-cpu-policy-v1'
def validate_prior_factory_policy(c):
    if 'prior_factory_policy' not in c:return None
    p=c['prior_factory_policy'];root=pathlib.Path(c['source_root']);r=c['prior_factory_policy_record'];rel=pathlib.PurePosixPath(r['relative_path'])
    require(not rel.is_absolute() and '..' not in rel.parts,'PRIOR_POLICY_PATH_ESCAPE')
    path=root/rel;require(path.resolve()==path,'PRIOR_POLICY_SYMLINK')
    raw=path.read_bytes();source={x['path']:x['sha256'] for x in c['source_records']}
    require(hashlib.sha256(raw).hexdigest()==r['sha256']==source.get(str(rel)),'PRIOR_POLICY_SHA_DRIFT')
    require(json.loads(raw)==p and p['schema']==SCHEMA,'PRIOR_POLICY_CONTENT_DRIFT')
    require(p['weight_loading_allowed'] is False and p['CUDA_allowed'] is False and p['forward_allowed'] is False,'PRIOR_CPU_POLICY_SCOPE_DRIFT')
    require(p['metric3d_factory']==dict(function='metric3d_vit_large',kwargs={'pretrain':False}),'METRIC_FACTORY_POLICY_DRIFT')
    require(p['timm_factory']==dict(model_name='vit_small_patch14_reg4_dinov2.lvd142m',kwargs=dict(pretrained=False,num_classes=0,dynamic_img_size=True,dynamic_img_pad=False)),'TIMM_FACTORY_POLICY_DRIFT')
    prefix='baselines/droid_w/prior_sources/Metric3D/';entry='mono/configs/HourglassDecoder/vit.raft5.large.py'
    require(p['metric3d_entry_config']==entry,'PRIOR_CONFIG_ENTRY_DRIFT')
    rows=p['metric3d_config_sources'];lookup={x['relative_path']:x for x in rows};require(len(rows)==len(lookup),'PRIOR_CONFIG_DUPLICATE')
    discovered=[]
    for rel,row in lookup.items():
        rp=pathlib.PurePosixPath(rel);require(not rp.is_absolute() and '..' not in rp.parts,'PRIOR_CONFIG_PATH_ESCAPE')
        cfg=root/prefix/rel;require(cfg.resolve()==cfg,'PRIOR_CONFIG_SYMLINK');data=cfg.read_bytes()
        require(hashlib.sha256(data).hexdigest()==row['sha256']==source.get(prefix+rel),'PRIOR_CONFIG_SHA_DRIFT')
        tree=ast.parse(data);bases=[]
        for n in tree.body:
            require(isinstance(n,(ast.Assign,ast.Import)),'PRIOR_CONFIG_EXECUTABLE_STATEMENT')
            if isinstance(n,ast.Import):require([x.name for x in n.names]==['numpy'],'PRIOR_CONFIG_IMPORT_DRIFT')
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_base_' for t in n.targets):bases=ast.literal_eval(n.value)
        for request in bases:
            target=(cfg.parent/request).resolve();repair=rel==entry and request=='../_base_/datasets/_data_base_.py'
            if repair:target=root/prefix/'mono/configs/_base_/_data_base_.py'
            require(target.is_relative_to(root/prefix),'PRIOR_CONFIG_EDGE_ESCAPE')
            target_rel=str(target.relative_to(root/prefix));require(target_rel in lookup,'PRIOR_CONFIG_EDGE_UNKNOWN')
            discovered.append(dict(declaring_relative_path=rel,requested_relative_path=request,target_relative_path=target_rel,sha256=lookup[target_rel]['sha256'],path_repaired=repair))
    require(sorted(discovered,key=str)==sorted(p['metric3d_config_edges'],key=str),'PRIOR_CONFIG_EDGE_DRIFT')
    seen=set();pending=[entry]
    while pending:
        v=pending.pop()
        if v in seen:continue
        seen.add(v);pending.extend(e['target_relative_path'] for e in discovered if e['declaring_relative_path']==v)
    require(seen==set(lookup),'PRIOR_CONFIG_CLOSURE_DRIFT')
    return dict(status='VERIFIED',sources=len(rows),edges=len(discovered),path_repairs=sum(x['path_repaired'] for x in discovered),policy_sha256=r['sha256'])
