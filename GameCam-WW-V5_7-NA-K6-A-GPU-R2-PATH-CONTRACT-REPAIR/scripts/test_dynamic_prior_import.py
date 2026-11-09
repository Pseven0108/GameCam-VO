"""CPU source identity, import semantics and direct Hub adapter regression."""
import concurrent.futures,hashlib,importlib,importlib.util,os,pathlib,sys,threading,time,types
import pytest
from verified_dynamic_source import VerifiedSourceFinder,SourceIdentityError

def build(tmp_path,files):
 records=[]
 for name,data in files.items():
  p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
  records.append(dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
 return VerifiedSourceFinder(tmp_path,records,candidate_sha256='a'*64)
def test_verified_byte_buffer_and_metadata(tmp_path):
 f=build(tmp_path,{'entry.py':'VALUE=42\n'});m=f.load_dynamic('verified_entry',tmp_path/'entry.py',temporary=True)
 assert m.VALUE==42 and m.__file__==str(tmp_path/'entry.py') and m.__spec__.origin==m.__file__ and m.__loader__.__class__.__name__=='VerifiedDynamicSourceLoader'
 assert m.__package__=='' and 'verified_entry' not in sys.modules
 assert [x['event'] for x in f.events]==['source_import_started','source_bytes_verified','source_import_completed']
@pytest.mark.parametrize('case',['unregistered','pyc','outside_root','traversal','relative','modified','wrong_sha','missing','replacement','symlink_leaf','symlink_parent','directory_as_py','fifo_as_py'])
def test_identity_rejections(tmp_path,case):
 f=build(tmp_path,{'entry.py':'VALUE=1\n'});p=tmp_path/'entry.py'
 if case=='unregistered':p=tmp_path/'unknown.py';p.write_text('VALUE=1')
 elif case=='pyc':p=tmp_path/'entry.pyc'
 elif case=='outside_root':p=tmp_path.parent/'outside.py'
 elif case=='traversal':p=tmp_path/'sub/../entry.py'
 elif case=='relative':p=pathlib.Path('entry.py')
 elif case=='modified':p.write_text('VALUE=2\n')
 elif case=='wrong_sha':f.records[str(p)]['sha256']='0'*64
 elif case=='missing':p.unlink()
 elif case=='replacement':q=tmp_path/'swap';q.write_text('VALUE=3\n');q.replace(p)
 elif case=='symlink_leaf':q=tmp_path/'other';p.rename(q);p.symlink_to(q)
 elif case=='symlink_parent':
  d=tmp_path/'real';d.mkdir();q=d/'entry.py';p.rename(q);(tmp_path/'alias').symlink_to(d,target_is_directory=True);p=tmp_path/'alias/entry.py';f.records[str(p)]=dict(path=str(p),sha256=hashlib.sha256(q.read_bytes()).hexdigest())
 elif case=='directory_as_py':p.unlink();p.mkdir()
 elif case=='fifo_as_py':p.unlink();os.mkfifo(p)
 with pytest.raises((SourceIdentityError,OSError)):f.load_dynamic('deny_'+case,p,temporary=True)
 assert 'deny_'+case not in sys.modules

def test_same_verified_bytes_used_after_hash(tmp_path):
 f=build(tmp_path,{'entry.py':'VALUE=17\n'});spec=f.spec('toctou',tmp_path/'entry.py');old=spec.loader.source_to_code
 def changed(data,path,*a,**kw):
  pathlib.Path(path).write_text('VALUE=999\n');return old(data,path,*a,**kw)
 spec.loader.source_to_code=changed;m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.VALUE==17 and (tmp_path/'entry.py').read_text()=='VALUE=999\n'

def test_package_relative_cycles_and_cache(tmp_path):
 f=build(tmp_path,{'dp_pkg/__init__.py':'from . import a\nVALUE=a.VALUE\n','dp_pkg/a.py':'from . import b\nVALUE=b.VALUE\n','dp_pkg/b.py':'import dp_pkg\nVALUE=9\n'}).install();sys.path.insert(0,str(tmp_path))
 try:
  m=importlib.import_module('dp_pkg');assert m.VALUE==9 and m.a.b is sys.modules['dp_pkg.b'];assert m.__package__=='dp_pkg' and m.__path__==[str(tmp_path/'dp_pkg')]
  count=len(f.events);assert importlib.import_module('dp_pkg') is m and len(f.events)==count
 finally:
  sys.meta_path.remove(f);sys.path.remove(str(tmp_path))
  for n in list(sys.modules):
   if n=='dp_pkg' or n.startswith('dp_pkg.'):sys.modules.pop(n,None)

def test_failed_import_cleans_modules(tmp_path):
 f=build(tmp_path,{'failed.py':'raise ValueError("expected-import-failure")\n'}).install();sys.path.insert(0,str(tmp_path))
 try:
  with pytest.raises(ValueError,match='expected-import-failure'):importlib.import_module('failed')
  assert 'failed' not in sys.modules and f.events[-1]['decision']=='DENY'
 finally:sys.meta_path.remove(f);sys.path.remove(str(tmp_path))

def test_relative_import_failure(tmp_path):
 f=build(tmp_path,{'entry.py':'from . import missing\n'})
 with pytest.raises(ImportError):f.load_dynamic('no_parent',tmp_path/'entry.py')
 assert 'no_parent' not in sys.modules

def test_thread_import_lock(tmp_path):
 f=build(tmp_path,{'threaded_dp.py':'import time\ntime.sleep(0.03)\nVALUE=object()\n'}).install();sys.path.insert(0,str(tmp_path))
 try:
  with concurrent.futures.ThreadPoolExecutor(4) as ex:mods=list(ex.map(lambda _:importlib.import_module('threaded_dp'),range(8)))
  assert all(m is mods[0] for m in mods) and sum(x['event']=='source_import_completed' for x in f.events)==1
 finally:sys.meta_path.remove(f);sys.path.remove(str(tmp_path));sys.modules.pop('threaded_dp',None)

def test_direct_hub_scoped_and_restored(tmp_path):
 f=build(tmp_path,{'hubconf.py':'VALUE=12\n'});old=lambda *a:None;hub=types.SimpleNamespace(_import_module=old);f.bind_torch_hub(hub,[dict(requested_path=str(tmp_path/'hubconf.py'),real_path=str(tmp_path/'hubconf.py'))])
 first=hub._import_module('hubconf.py',str(tmp_path/'hubconf.py'));second=hub._import_module('hubconf.py',str(tmp_path/'hubconf.py'))
 assert first.VALUE==second.VALUE==12 and first is not second and 'hubconf.py' not in sys.modules
 with pytest.raises(SourceIdentityError):hub._import_module('anything',str(tmp_path/'unknown.py'))
 f.restore_torch_hub();assert hub._import_module is old

def test_direct_failure_restores_previous_module(tmp_path):
 f=build(tmp_path,{'entry.py':'raise RuntimeError("direct-bad")\n'});previous=types.ModuleType('direct_fail');sys.modules['direct_fail']=previous
 try:
  with pytest.raises(RuntimeError,match='direct-bad'):f.load_dynamic('direct_fail',tmp_path/'entry.py',temporary=True)
  assert sys.modules['direct_fail'] is previous
 finally:sys.modules.pop('direct_fail',None)

def test_no_bytecode_probe_even_if_bad_cache_exists(tmp_path):
 f=build(tmp_path,{'entry.py':'VALUE=51\n'});d=tmp_path/'__pycache__';d.mkdir();(d/'entry.cpython-310.pyc').write_bytes(b'not-valid-cache')
 assert f.load_dynamic('no_cache',tmp_path/'entry.py',temporary=True).VALUE==51

def test_foreign_external_root_rejected(tmp_path):
 with pytest.raises(SourceIdentityError):VerifiedSourceFinder(tmp_path,[],[dict(path='/outside/source.py',sha256='0'*64)])

def test_loader_cannot_read_other_path(tmp_path):
 f=build(tmp_path,{'entry.py':'VALUE=1\n'});loader=f.spec('e',tmp_path/'entry.py').loader
 with pytest.raises(SourceIdentityError):loader.get_data(str(tmp_path/'__pycache__/entry.pyc'))
 with pytest.raises(SourceIdentityError):loader.set_data('cache.pyc',b'x')


def test_parent_directory_race_rejected_before_bytes_used(tmp_path,monkeypatch):
 source_dir=tmp_path/'trusted';source_dir.mkdir();f=build(tmp_path,{'trusted/entry.py':'VALUE=1\n'});other=tmp_path/'other';other.mkdir();(other/'entry.py').write_text('VALUE=1\n')
 original=os.open;done=[]
 def raced(path,flags,*args,**kwargs):
  if str(path)==str(source_dir/'entry.py') and not done:
   source_dir.rename(tmp_path/'original');source_dir.symlink_to(other,target_is_directory=True);done.append(True)
  return original(path,flags,*args,**kwargs)
 monkeypatch.setattr(os,'open',raced)
 with pytest.raises(SourceIdentityError,match='DESCRIPTOR_ESCAPE'):f.load_dynamic('race_parent',source_dir/'entry.py',temporary=True)
 assert 'race_parent' not in sys.modules

@pytest.mark.parametrize('bad',['missing_policy','allow_pyc','allow_network','modified_manifest','wrong_entry_sha','extra_entry','source_sha','external_sha','partial_manifest'])
def test_dynamic_policy_fail_closed(tmp_path,bad):
 from dynamic_source_policy import validate_dynamic_source_policy
 sources=[]
 for name in ('Metric3D','FiT3D'):
  rel='baselines/droid_w/prior_sources/'+name+'/hubconf.py';p=tmp_path/rel;p.parent.mkdir(parents=True);p.write_text('VALUE=1\n');sources.append(dict(path=rel,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
 manifest=dict(schema='gamecam-dynamic-source-manifest-v1',sources=sources.copy());m=tmp_path/'manifest.json';m.write_text(__import__('json').dumps(manifest));mr=dict(path='manifest.json',sha256=hashlib.sha256(m.read_bytes()).hexdigest())
 ext='/prod/GameCam-VO';c=dict(source_root=str(tmp_path),external_production_root=ext,source_records=sources+[mr],external_source_records=[dict(path=ext+'/'+r['path'],sha256=r['sha256']) for r in sources],dynamic_source_policy=dict(version='gamecam-verified-dynamic-source-v1',strategy='VERIFIED_SOURCE_ONLY',allow_project_bytecode=False,allow_network=False,manifest_record=dict(relative_path='manifest.json',sha256=mr['sha256']),hub_entrypoints=[dict(requested_path='/mnt/d/aaa/GameCam-VO/'+r['path'],real_path=ext+'/'+r['path'],sha256=r['sha256']) for r in sources]))
 assert validate_dynamic_source_policy(c)['sources']==2
 if bad=='missing_policy':c.pop('dynamic_source_policy')
 elif bad=='allow_pyc':c['dynamic_source_policy']['allow_project_bytecode']=True
 elif bad=='allow_network':c['dynamic_source_policy']['allow_network']=True
 elif bad=='modified_manifest':m.write_text('{}')
 elif bad=='wrong_entry_sha':c['dynamic_source_policy']['hub_entrypoints'][0]['sha256']='0'*64
 elif bad=='extra_entry':c['dynamic_source_policy']['hub_entrypoints'].append(c['dynamic_source_policy']['hub_entrypoints'][0])
 elif bad=='source_sha':c['source_records'][0]['sha256']='0'*64
 elif bad=='external_sha':c['external_source_records'][0]['sha256']='0'*64
 elif bad=='partial_manifest':
  manifest['sources']=sources[:1];m.write_text(__import__('json').dumps(manifest));newsha=hashlib.sha256(m.read_bytes()).hexdigest();mr['sha256']=newsha;c['dynamic_source_policy']['manifest_record']['sha256']=newsha
 with pytest.raises(RuntimeError):validate_dynamic_source_policy(c)


@pytest.mark.parametrize('case',['valid','unregistered','pyc','modified','wrong_sha','symlink','traversal','outside_root','deleted','replacement'])
def test_real_model_boundary_and_loader_subprocess(tmp_path,case):
 import subprocess
 script=r'''
import hashlib,json,pathlib,sys
from verified_dynamic_source import VerifiedSourceFinder
from model_io_boundary_v2 import ModelIOBoundary
root=pathlib.Path(sys.argv[1]);root.mkdir();p=root/'entry.py';p.write_text('VALUE=23\n');row=dict(path='entry.py',sha256=hashlib.sha256(p.read_bytes()).hexdigest());f=VerifiedSourceFinder(root,[row])
case=sys.argv[2];target=p
if case=='unregistered':target=root/'other.py';target.write_text('VALUE=99\n')
elif case=='pyc':target=root/'__pycache__/entry.cpython-310.pyc'
elif case=='modified':p.write_text('VALUE=99\n')
elif case=='wrong_sha':f.records[str(p)]['sha256']='0'*64
elif case=='symlink':q=root/'other';p.rename(q);p.symlink_to(q)
elif case=='traversal':target=root/'sub/../entry.py'
elif case=='outside_root':target=root.parent/'outside.py'
elif case=='deleted':p.unlink()
elif case=='replacement':q=root/'replacement';q.write_text('VALUE=99\n');q.replace(p)
b=ModelIOBoundary([], [p], [root], [], []);b.install();denied=None
try:m=f.load_dynamic('cpu_boundary_case',target,temporary=True)
except (RuntimeError,OSError) as exc:denied=str(exc)
assert (denied is None)==(case=='valid')
assert 'cpu_boundary_case' not in sys.modules
print(json.dumps(dict(case=case,denied=denied,boundary_events=b.events,loader_events=f.events)))
'''
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPYCACHEPREFIX',None)
 p=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path/'boundary'),case],env=env,capture_output=True,text=True,timeout=10)
 assert p.returncode==0,p.stdout+p.stderr


def test_frozen_hub_alias_cannot_be_redirected(tmp_path):
 f=build(tmp_path,{'hubconf.py':'VALUE=1\n','other.py':'VALUE=2\n'});alias=tmp_path/'alias.py';alias.symlink_to(tmp_path/'hubconf.py');hub=types.SimpleNamespace(_import_module=lambda *a:None)
 # Only the historical hubconf filename and exact frozen target may be bound.
 d=tmp_path/'alias';d.mkdir();alias=d/'hubconf.py';alias.symlink_to(tmp_path/'hubconf.py')
 f.bind_torch_hub(hub,[dict(requested_path=str(alias),real_path=str(tmp_path/'hubconf.py'))])
 assert hub._import_module('hubconf',str(alias)).VALUE==1
 alias.unlink();alias.symlink_to(tmp_path/'other.py')
 with pytest.raises(SourceIdentityError,match='ALIAS_IDENTITY_DRIFT'):hub._import_module('hubconf',str(alias))
 f.restore_torch_hub()


def test_direct_hub_uses_canonical_package_origin_and_restores_sys_path(tmp_path):
 f=build(tmp_path,{'hubconf.py':'import hubpkg\nVALUE=hubpkg.VALUE\n','hubpkg/__init__.py':'from .child import VALUE\n','hubpkg/child.py':'VALUE=61\n'}).install();alias=tmp_path.parent/(tmp_path.name+'-alias');alias.symlink_to(tmp_path,target_is_directory=True);hub=types.SimpleNamespace(_import_module=lambda *a:None)
 f.bind_torch_hub(hub,[dict(requested_path=str(alias/'hubconf.py'),real_path=str(tmp_path/'hubconf.py'))]);sys.path.insert(0,str(alias));original=list(sys.path)
 try:
  m=hub._import_module('hubconf.py',str(alias/'hubconf.py'));assert m.VALUE==61
  assert sys.modules['hubpkg'].__file__==str(tmp_path/'hubpkg/__init__.py') and sys.path==original
 finally:
  f.restore_torch_hub();sys.meta_path.remove(f);sys.path.remove(str(alias));sys.modules.pop('hubpkg.child',None);sys.modules.pop('hubpkg',None)
