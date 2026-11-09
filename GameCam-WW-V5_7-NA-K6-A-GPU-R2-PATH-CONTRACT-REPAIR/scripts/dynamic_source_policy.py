"""Validate the SHA-bound dynamic-source closure without widening file IO."""
import hashlib,json,pathlib
from runtime_dependency_pins import require,digest_file
POLICY_VERSION='gamecam-verified-dynamic-source-v1'
SCHEMA_VERSION='gamecam-dynamic-source-manifest-v1'
def validate_dynamic_source_policy(c):
    p=c.get('dynamic_source_policy',{})
    require(p.get('version')==POLICY_VERSION and p.get('strategy')=='VERIFIED_SOURCE_ONLY','DYNAMIC_SOURCE_POLICY_MISSING_OR_DRIFT')
    require(p.get('allow_project_bytecode') is False and p.get('allow_network') is False,'DYNAMIC_SOURCE_POLICY_UNSAFE')
    root=pathlib.Path(c['source_root']);r=p['manifest_record'];mfile=root/r['relative_path']
    require(not pathlib.PurePosixPath(r['relative_path']).is_absolute() and '..' not in pathlib.PurePosixPath(r['relative_path']).parts,'DYNAMIC_MANIFEST_PATH_ESCAPE')
    require(mfile.resolve()==mfile,'DYNAMIC_MANIFEST_IDENTITY_DRIFT')
    raw=mfile.read_bytes();require(hashlib.sha256(raw).hexdigest()==r['sha256'],'DYNAMIC_MANIFEST_IDENTITY_DRIFT')
    manifest=json.loads(raw);require(manifest['schema']==SCHEMA_VERSION,'DYNAMIC_MANIFEST_SCHEMA')
    source={x['path']:x['sha256'] for x in c['source_records']}
    require(source.get(r['relative_path'])==r['sha256'],'DYNAMIC_MANIFEST_NOT_SOURCE_BOUND')
    rows=manifest['sources'];seen=set()
    external={x['path']:x['sha256'] for x in c.get('external_source_records',[])}
    for x in rows:
        rel=pathlib.PurePosixPath(x['path']);require(not rel.is_absolute() and '..' not in rel.parts and rel.suffix=='.py','DYNAMIC_SOURCE_MANIFEST_PATH')
        require(str(rel).startswith(('baselines/droid_w/prior_sources/Metric3D/','baselines/droid_w/prior_sources/FiT3D/')),'DYNAMIC_MANIFEST_PRIOR_ROOT')
        require(str(rel) not in seen and source.get(str(rel))==x['sha256'],'DYNAMIC_MANIFEST_SOURCE_SHA_OR_DUPLICATE');seen.add(str(rel))
        expected=str(pathlib.Path(c['external_production_root'])/rel)
        require(external.get(expected)==x['sha256'],'DYNAMIC_MANIFEST_EXTERNAL_SOURCE_SHA')
    expected_sources={k for k in source if k.endswith('.py') and k.startswith(('baselines/droid_w/prior_sources/Metric3D/','baselines/droid_w/prior_sources/FiT3D/'))}
    require(seen==expected_sources,'DYNAMIC_MANIFEST_CLOSURE_INCOMPLETE')
    expected_entries=[]
    for name in ('Metric3D','FiT3D'):
        rel='baselines/droid_w/prior_sources/'+name+'/hubconf.py'
        expected_entries.append(dict(requested_path='/mnt/d/aaa/GameCam-VO/'+rel,real_path=str(pathlib.Path(c['external_production_root'])/rel),sha256=source[rel]))
    require(p['hub_entrypoints']==expected_entries,'DYNAMIC_HUB_ENTRYPOINT_DRIFT')
    return dict(schema=SCHEMA_VERSION,sources=len(rows),hub_entrypoints=2,manifest_sha256=r['sha256'],status='VERIFIED')
