"""Verify retained local evidence before authorizing exact remote cleanup paths."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
P=ROOT.parents[1]
T=P/'experiments/task008_pi3mos'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

checks=[]
sources=[(T/'retrieved',T/'retrieved/RESULT_COLLECTION_MANIFEST.json'),
         (P/'reviews/task008-pi3mos-night007-independent-inference-20261126',P/'reviews/task008-pi3mos-night007-independent-inference-20261126/FILE_SHA256_MANIFEST.json'),
         (P/'reviews/task007d-metric-scale-provenance-audit-20261126',P/'reviews/task007d-metric-scale-provenance-audit-20261126/FILE_SHA256_MANIFEST.json')]
for base,manifest in sources:
    rows=json.loads(manifest.read_text('utf-8'))['files']
    for row in rows:
        f=base/row['path']
        assert f.resolve().is_relative_to(base.resolve()) and f.is_file()
        assert f.stat().st_size==row['bytes'] and digest(f)==row['sha256'],str(f)
    checks.append({'root':str(base),'files':len(rows),'SHA256':'PASS','bytes':sum(r['bytes'] for r in rows),'manifest_SHA256':digest(manifest)})

inventory=json.loads((ROOT/'inventory_current.json').read_text('utf-8'))
paths=[
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/wheelhouse',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/tmp',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R1/official_source_fresh_clone.bundle',
 '/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED/outputs',
 '/root/rivermind-data/external_models/pi3mos_task008_weights',
 '/opt/gamecam-pi3mos/envs/pi3mos-infer',
 '/root/rivermind-data/GAMECAM_TASK008_API_PUBLICATION_20261126_CONCURRENT/GAMECAM_TASK008_PI3MOS_NIGHT007_REVIEW.zip',
 '/root/rivermind-data/GAMECAM_TASK007D_PUBLICATION_20261126/GAMECAM_TASK007D_METRIC_SCALE_PROVENANCE_REVIEW.zip',
]
by_path={r['path']:r for r in inventory['target_inventory']}
rows=[]
for p in paths:
    if p=='/opt/gamecam-pi3mos/envs/pi3mos-infer':
        row={**by_path['/opt/gamecam-pi3mos'],'path':p}
    else:row=by_path[p]
    rows.append({**row,'reason':'TASK008 exclusive reusable environment' if p.startswith('/opt/') else 'TASK007D redundant published ZIP' if 'TASK007D' in p else 'TASK008 dedicated artifacts; retained evidence and reproducible downloads'})
output_files=[r for r in json.loads((T/'retrieved/RESULT_COLLECTION_MANIFEST.json').read_text('utf-8'))['files'] if r['path'].startswith('outputs/')]
published={}
for task in ['TASK007D','TASK008']:
    d=json.loads((P/('maintenance/GITHUB_'+task+'_PUBLICATION_20261126/PUBLICATION_VERIFIED.json')).read_text('utf-8'))
    published[task]={'commit':d['commit'],'ZIP':d['ZIP'],'ZIP_url':d['ZIP_url'],'release_url':d['release_url']}

plan={'client_date':'2026-11-27 Asia/Shanghai','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'authorization':'User requests stop TASK008, return to baseline optimization, and clean TASK008/TASK007D server storage.',
      'endpoint':'sc01-ssh.gpuhome.cc:31454','expected_hostname':inventory['hostname'],
      'local_backup_verification':checks,'deletion_targets':rows,'output_backup_files':output_files,
      'published_review_evidence':published,
      'do_not_delete':['DROID-W source/config/weights/extensions/environments','Metric3D weights','VIPER original data','historical experiments','expanded TASK007D/TASK008 reviews','local raw predictions'],
      'no_new_experiment_or_reboot':True}
(ROOT/'CLEANUP_AUTHORIZATION_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'local_verifications':checks,'targets':len(rows),'data_logical_bytes':sum(r['logical_bytes'] for r in rows if r['path'].startswith('/root/')),'system_logical_bytes':sum(r['logical_bytes'] for r in rows if r['path'].startswith('/opt/')),'raw_output_files_retain_local':len(output_files)},ensure_ascii=False,indent=2))
