"""Focused boundary regressions. Test stubs here are not model factory evidence."""
import copy,hashlib,json,pathlib,types
import pytest
from verified_dynamic_source import VerifiedSourceFinder,SourceIdentityError
from verified_config_dependency import VerifiedConfigDependency

def setup_adapter(tmp_path):
    root=tmp_path/'Metric3D';root.mkdir();entry='entry.py';base='base.py';records=[]
    for n,t in [(entry,"_base_=['missing/base.py']\n"),(base,'VALUE=7\n'),('hubconf.py','VALUE=1\n')]:
        p=root/n;p.write_text(t);records.append(dict(path=n,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
    finder=VerifiedSourceFinder(root,records);sha={x['path']:x['sha256'] for x in records}
    class Config:
        @staticmethod
        def _get_cfg_path(request,filename):return str(pathlib.Path(filename).parent/request),None
        @staticmethod
        def fromfile(filename):return Config._get_cfg_path('missing/base.py',filename)[0]
    policy=dict(schema='gamecam-prior-factory-cpu-policy-v1',metric3d_entry_config=entry,metric3d_config_sources=[dict(relative_path=x['path'],sha256=x['sha256']) for x in records if x['path']!='hubconf.py'],metric3d_config_edges=[dict(declaring_relative_path=entry,requested_relative_path='missing/base.py',target_relative_path=base,sha256=sha[base],path_repaired=True)])
    adapter=VerifiedConfigDependency(finder,policy);module=types.SimpleNamespace(Config=Config);old_get=Config._get_cfg_path;old_from=Config.fromfile
    adapter.on_hub_import(module,root/'hubconf.py');return root,finder,adapter,module,old_get,old_from

def test_exact_config_dependency_and_restore(tmp_path):
    r,f,a,m,g,frm=setup_adapter(tmp_path)
    assert m.Config.fromfile(str(r/'entry.py'))==str(r/'base.py')
    a.on_hub_import(m,r/'hubconf.py');a.restore();assert m.Config._get_cfg_path is g and m.Config.fromfile is frm

@pytest.mark.parametrize('requested',['unknown.py','../outside.py','/etc/passwd','base.py','missing/../base.py'])
def test_unknown_config_reference_denied(tmp_path,requested):
    r,f,a,m,_,_=setup_adapter(tmp_path)
    with pytest.raises(RuntimeError,match='NOT_ALLOWLISTED'):m.Config._get_cfg_path(requested,str(r/'entry.py'))

@pytest.mark.parametrize('kind',['wrong-entry','traversal','relative','entry-symlink','declaring-symlink','source-mutated','manifest-sha','target-traversal','target-symlink','binding-drift'])
def test_config_identity_fail_closed(tmp_path,kind):
    r,f,a,m,_,_=setup_adapter(tmp_path);entry=str(r/'entry.py')
    if kind=='wrong-entry':entry=str(r/'base.py')
    if kind=='traversal':entry=str(r/'sub/../entry.py')
    if kind=='relative':entry='entry.py'
    if kind=='entry-symlink':(r/'alias.py').symlink_to(r/'entry.py');entry=str(r/'alias.py')
    if kind=='source-mutated':(r/'base.py').write_text('VALUE=99\n')
    if kind=='manifest-sha':a.policy['metric3d_config_sources'][0]['sha256']='0'*64
    if kind=='target-traversal':a.policy['metric3d_config_edges'][0]['target_relative_path']='sub/../base.py'
    if kind=='target-symlink':p=r/'other.py';p.write_bytes((r/'base.py').read_bytes());(r/'base.py').unlink();(r/'base.py').symlink_to(p)
    with pytest.raises((RuntimeError,OSError)):
        if kind=='declaring-symlink':
            (r/'alias.py').symlink_to(r/'entry.py');m.Config._get_cfg_path('missing/base.py',str(r/'alias.py'))
        elif kind=='binding-drift':m.Config.fromfile=lambda *a:None;a.on_hub_import(m,r/'hubconf.py')
        else:m.Config.fromfile(entry)

def test_hub_lazy_callback_after_verified_source(tmp_path):
    p=tmp_path/'hubconf.py';p.write_text('VALUE=12\n');f=VerifiedSourceFinder(tmp_path,[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())]);hub=types.SimpleNamespace(_import_module=lambda *a:None);seen=[]
    f.bind_torch_hub(hub,[dict(requested_path=str(p),real_path=str(p))],after_source_import=lambda m,p:seen.append((m.VALUE,p)))
    assert hub._import_module('hubconf',str(p)).VALUE==12 and seen==[(12,str(p))]
    f.restore_torch_hub()

from prior_factory_policy import validate_prior_factory_policy
def policy_candidate(tmp_path):
    prefix='baselines/droid_w/prior_sources/Metric3D/';entry='mono/configs/HourglassDecoder/vit.raft5.large.py';base='mono/configs/_base_/_data_base_.py';rows=[];sources=[]
    for rel,text in [(entry,"_base_=['../_base_/datasets/_data_base_.py']\n"),(base,'VALUE=7\n')]:
        f=tmp_path/prefix/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text);sha=hashlib.sha256(f.read_bytes()).hexdigest();rows.append(dict(relative_path=rel,sha256=sha));sources.append(dict(path=prefix+rel,sha256=sha))
    p=dict(schema='gamecam-prior-factory-cpu-policy-v1',metric3d_entry_config=entry,metric3d_config_sources=rows,metric3d_config_edges=[dict(declaring_relative_path=entry,requested_relative_path='../_base_/datasets/_data_base_.py',target_relative_path=base,sha256=rows[1]['sha256'],path_repaired=True)],metric3d_factory=dict(function='metric3d_vit_large',kwargs={'pretrain':False}),timm_factory=dict(model_name='vit_small_patch14_reg4_dinov2.lvd142m',kwargs=dict(pretrained=False,num_classes=0,dynamic_img_size=True,dynamic_img_pad=False)),weight_loading_allowed=False,CUDA_allowed=False,forward_allowed=False)
    file=tmp_path/'policy.json';file.write_text(json.dumps(p));sha=hashlib.sha256(file.read_bytes()).hexdigest();sources.append(dict(path='policy.json',sha256=sha));return dict(source_root=str(tmp_path),source_records=sources,prior_factory_policy=p,prior_factory_policy_record=dict(relative_path='policy.json',sha256=sha))

def test_policy_is_candidate_bound(tmp_path):
    c=policy_candidate(tmp_path);r=validate_prior_factory_policy(c);assert r['sources']==2 and r['path_repairs']==1

@pytest.mark.parametrize('change',['record_sha','source_sha','embedded_policy','entry_escape','unsafe_cuda','unknown_edge','config_mutation','policy_symlink'])
def test_policy_drift_rejected(tmp_path,change):
    c=policy_candidate(tmp_path)
    if change=='record_sha':c['prior_factory_policy_record']['sha256']='0'*64
    if change=='source_sha':c['source_records'][-1]['sha256']='0'*64
    if change=='embedded_policy':c['prior_factory_policy']['forward_allowed']=True
    if change=='config_mutation':(tmp_path/c['source_records'][0]['path']).write_text('VALUE=99\n')
    if change=='policy_symlink':f=tmp_path/'policy.json';f.rename(tmp_path/'target.json');f.symlink_to(tmp_path/'target.json')
    if change in ('entry_escape','unsafe_cuda','unknown_edge'):
        p=c['prior_factory_policy']
        if change=='entry_escape':p['metric3d_entry_config']='../outside.py'
        if change=='unsafe_cuda':p['CUDA_allowed']=True
        if change=='unknown_edge':p['metric3d_config_edges'][0]['requested_relative_path']='unknown.py'
        f=tmp_path/'policy.json';f.write_text(json.dumps(p));sha=hashlib.sha256(f.read_bytes()).hexdigest();c['prior_factory_policy_record']['sha256']=sha;c['source_records'][-1]['sha256']=sha
    with pytest.raises((RuntimeError,OSError)):validate_prior_factory_policy(c)

from prior_factory_cpu_guard import CPUFactoryGuard
def test_native_safe_open_denied_before_original(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','');g=CPUFactoryGuard();called=[];m=types.SimpleNamespace(__name__='safetensors',safe_open=lambda *a,**kw:called.append(a))
    g.patch_dependency(m);first=m.safe_open;g.patch_dependency(m);assert m.safe_open is first
    with pytest.raises(RuntimeError,match='CHECKPOINT_API_FORBIDDEN'):m.safe_open('/not-read/sentinel.safetensors',framework='pt')
    assert not called and g.events[-1]['request']=='safetensors.safe_open'

def test_cpu_guard_requires_empty_visibility(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','0')
    with pytest.raises(RuntimeError,match='DEVICE_MASK_REQUIRED'):CPUFactoryGuard()

def test_policy_canonical_json_preserves_edge_identity(tmp_path):
    c=policy_candidate(tmp_path);p=c['prior_factory_policy'];prefix='baselines/droid_w/prior_sources/Metric3D/';entry=tmp_path/c['source_records'][0]['path'];entry.write_text("_base_=['../_base_/datasets/_data_base_.py','../_base_/default_runtime.py']\n")
    sha=hashlib.sha256(entry.read_bytes()).hexdigest();c['source_records'][0]['sha256']=sha;p['metric3d_config_sources'][0]['sha256']=sha
    rel='mono/configs/_base_/default_runtime.py';f=tmp_path/prefix/rel;f.write_text('VALUE=8\n');sha=hashlib.sha256(f.read_bytes()).hexdigest();c['source_records'].append(dict(path=prefix+rel,sha256=sha));p['metric3d_config_sources'].append(dict(relative_path=rel,sha256=sha));p['metric3d_config_edges'].append(dict(declaring_relative_path=p['metric3d_entry_config'],requested_relative_path='../_base_/default_runtime.py',target_relative_path=rel,sha256=sha,path_repaired=False))
    p=json.loads(json.dumps(p,sort_keys=True));c['prior_factory_policy']=p;f=tmp_path/'policy.json';f.write_text(json.dumps(p,sort_keys=True));sha=hashlib.sha256(f.read_bytes()).hexdigest();c['prior_factory_policy_record']['sha256']=sha
    next(r for r in c['source_records'] if r['path']=='policy.json')['sha256']=sha
    assert validate_prior_factory_policy(c)['edges']==2
