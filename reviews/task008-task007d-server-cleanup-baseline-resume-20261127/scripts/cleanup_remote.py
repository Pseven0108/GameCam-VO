"""Delete only eight explicitly authorized, identity-checked TASK008/TASK007D paths."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

# PLAN is injected by the local CPU launcher, after backup verification.
AUDIT=Path('/root/rivermind-data/GAMECAM_TASK008_TASK007D_CLEANUP_20261127')
R2=Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(name,data):
    p=AUDIT/name
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def volumes():return {p:dict(zip(['total','used','free'],shutil.disk_usage(p))) for p in ['/','/root/rivermind-data','/dev/shm']}
def items(root):
    if root.is_file():yield root;return
    for current,dirs,files in os.walk(root,followlinks=False):
        for n in list(dirs):
            p=Path(current,n)
            if p.is_symlink():dirs.remove(n);yield p
        for n in files:yield Path(current,n)
def identity(p):
    s=p.lstat()
    r={'path':str(p),'bytes':s.st_size,'device':s.st_dev,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'mode':stat.S_IMODE(s.st_mode),'hardlinks':s.st_nlink}
    if p.is_symlink():r['symlink_target']=os.readlink(p)
    return r
def active_refs(targets):
    hits=[]
    def matches(x):return any(x==str(t) or x.startswith(str(t)+'/') for t in targets)
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            probes=[]
            for k in ['cwd','exe']:
                try:probes.append((k,os.readlink(p/k).removesuffix(' (deleted)')))
                except OSError:pass
            try:
                for f in (p/'fd').iterdir():
                    try:probes.append(('fd',os.readlink(f).removesuffix(' (deleted)')))
                    except OSError:pass
            except OSError:pass
            try:
                for line in (p/'maps').read_text(errors='replace').splitlines():
                    parts=line.split(None,5)
                    if len(parts)==6 and parts[5].startswith('/'):probes.append(('map',parts[5].removesuffix(' (deleted)')))
            except OSError:pass
            for kind,value in probes:
                if matches(value):hits.append({'pid':int(p.name),'kind':kind,'path':value})
        except OSError:pass
    return hits

assert os.uname().nodename==PLAN['expected_hostname']
assert all(x['SHA256']=='PASS' for x in PLAN['local_backup_verification'])
assert json.loads((R2/'INFERENCE_EXIT_RECEIPT.json').read_text())['exit_code']==0
assert json.loads((R2/'INFERENCE_STATE.json').read_text())['model_forwards_complete']==64
targets=[Path(r['path']) for r in PLAN['deletion_targets']]
assert len(targets)==8 and len(set(targets))==8
assert not any(a!=b and a.is_relative_to(b) for a in targets for b in targets)
expected_paths={
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/wheelhouse',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/tmp',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/official_source_fresh_clone.bundle',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED/outputs',
 '/root/rivermind-data/external_models/pi3mos_task008_weights',
 '/opt/gamecam-pi3mos/envs/pi3mos-infer',
 '/root/rivermind-data/GAMECAM_TASK008_API_PUBLICATION_20261126_CONCURRENT/GAMECAM_TASK008_PI3MOS_NIGHT007_REVIEW.zip',
 '/root/rivermind-data/GAMECAM_TASK007D_PUBLICATION_20261126/GAMECAM_TASK007D_METRIC_SCALE_PROVENANCE_REVIEW.zip'}
assert set(map(str,targets))==expected_paths
for p in targets:
    assert p.exists() and not p.is_symlink() and p.resolve()==p
assert not active_refs(targets),'An authorized target is still in use; no deletion performed'

protected={r['path']:r for r in json.loads((R2/'BASELINE_PROTECTION_BEFORE.json').read_text())['files']}
for r in json.loads((R2/'INPUT_IDENTITY_BEFORE.json').read_text())['frames']:protected[r['path']]=r
rgb=Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487')
for p in rgb.iterdir():
    if p.is_file() and p.suffix.lower() in ['.jpg','.jpeg','.png'] and str(p) not in protected:
        protected[str(p)]={'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
manifest=Path('/root/rivermind-data/VIPER_MATCHED_DUAL_BASELINE_R2/manifests/val_007_full_00001-00487.json')
protected[str(manifest)]={'path':str(manifest),'bytes':manifest.stat().st_size,'sha256':sha(manifest)}
before=[]
for path,r in sorted(protected.items()):
    p=Path(path)
    assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'Protected baseline differs before cleanup: '+path
    assert not any(p.is_relative_to(t) or p.resolve().is_relative_to(t) for t in targets)
    before.append({**identity(p),'sha256':r['sha256']})
for r in PLAN['output_backup_files']:
    p=R2/r['path'];assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'Remote/local output backup differs'
weight=Path('/root/rivermind-data/external_models/pi3mos_task008_weights/pi3mos_official.pth')
assert sha(weight)=='1a536b1bb6e9c6c16a77b7ed544649351d387e281a16f3d946e0786cdcf23ded'
for p in targets:
    if p.suffix=='.zip':
        task='TASK007D' if 'TASK007D' in str(p) else 'TASK008'
        assert sha(p)==PLAN['published_review_evidence'][task]['ZIP']['ZIP_sha256']

deletion_inventory=[]
for target,expected in zip(targets,PLAN['deletion_targets']):
    rows=[identity(p) for p in sorted(items(target))]
    regular=[r for r in rows if 'symlink_target' not in r]
    assert len(regular)==expected['files'] and sum(r['bytes'] for r in regular)==expected['logical_bytes'],'Target changed since inventory: '+str(target)
    deletion_inventory.append({'root':identity(target),'reason':expected['reason'],'files':rows,'logical_bytes':sum(r['bytes'] for r in regular)})

AUDIT.mkdir(mode=0o700,exist_ok=False)
write('CLEANUP_AUTHORIZATION_PLAN.json',PLAN)
write('PROTECTED_FILES_BEFORE.json',{'files':before})
write('DELETION_INVENTORY_BEFORE.json',{'targets':deletion_inventory})
start=volumes();done=[]
write('RESOURCE_BEFORE.json',start)
write('PROGRESS.json',{'state':'ALL_TARGETS_IDENTIFIED_AND_BACKUPS_VERIFIED','deleted':done})
for target,inventory in zip(targets,deletion_inventory):
    assert not active_refs([target]),'Target became in-use; stopping remaining cleanup'
    assert identity(target)==inventory['root'],'Target identity changed before deletion'
    if target.is_dir():
        assert shutil.rmtree.avoids_symlink_attacks
        shutil.rmtree(target)
    else:target.unlink()
    assert not target.exists() and not target.is_symlink()
    done.append({'path':str(target),'logical_bytes':inventory['logical_bytes'],'regular_files':sum('symlink_target' not in x for x in inventory['files']),'removed':True})
    write('PROGRESS.json',{'state':'DELETING_ONLY_APPROVED_PATHS','deleted':done})

registration=Path('/root/.conda/environments.txt')
registry_result={'exists':registration.exists(),'only_target_registration_removed':False}
if registration.is_file():
    raw=registration.read_bytes();text=raw.decode();lines=text.splitlines(keepends=True)
    kept=[line for line in lines if line.strip()!='/opt/gamecam-pi3mos/envs/pi3mos-infer']
    if kept!=lines:
        (AUDIT/'CONDA_ENVIRONMENTS_REGISTRATION_BEFORE.txt').write_bytes(raw)
        registration.write_bytes(''.join(kept).encode())
        registry_result.update(only_target_registration_removed=True,removed_lines=len(lines)-len(kept),before_sha256=hashlib.sha256(raw).hexdigest(),after_sha256=sha(registration))

after=[]
for r in before:
    p=Path(r['path']);actual={**identity(p),'sha256':sha(p)}
    assert actual==r,'Protected original changed during cleanup: '+str(p)
    after.append(actual)
write('PROTECTED_FILES_AFTER.json',{'files':after,'all_identical':True})
end=volumes()
disposition={'client_date':'2026-11-27 Asia/Shanghai','TASK008':'STOPPED_AND_PARKED_BY_USER','TASK007D':'AUDIT_SEALED_REPEATED_SERVER_ZIP_REMOVED',
             'research_direction':'DROID-W BASELINE OPTIMIZATION','new_experiment_started':False,'GPU_used':False,'instance_reboot_or_shutdown':False,
             'raw_predictions_retained_local':PLAN['local_backup_verification'][0]['root'],'remote_predictions_deleted':True,
             'existing_reports_configs_source_and_baselines_retained':True}
for root in [R2,Path('/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1')]:
    with (root/'USER_STOP_AND_STORAGE_CLEANUP_20261127.json').open('x') as f:json.dump(disposition,f,indent=2)
write('STAGE_DISPOSITION.json',disposition)
result={'status':'CLEANUP_COMPLETED_AND_BASELINE_ASSETS_PRESERVED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'deleted':done,'before':start,'after':end,'free_space_change_bytes':{k:end[k]['free']-start[k]['free'] for k in start},
        'protected_files_verified':len(before),'output_backup_files_verified':len(PLAN['output_backup_files']),
        'protected_SHA256_identity':'PASS','environment_registration':registry_result,'disposition':disposition,
        'audit_directory':str(AUDIT)}
write('CLEANUP_FINAL_RECEIPT.json',result);write('PROGRESS.json',{'state':'COMPLETE','deleted':done})
print(json.dumps(result,ensure_ascii=False,indent=2))
