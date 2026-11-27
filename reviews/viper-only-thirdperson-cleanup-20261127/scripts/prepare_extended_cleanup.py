"""Extend the exact deletion plan to user-authorized earliest third-person studies."""
from pathlib import Path
import gzip, hashlib, json, os, shutil, stat

OUT=Path(__file__).resolve().parent
BASE=Path('D:/aaa/GameCam-VO');WORK=Path('D:/aaa')
old=json.loads((OUT/'LOCAL_DELETION_PLAN.json').read_text(encoding='utf-8'))
protected=json.loads((OUT/'PROTECTED_BEFORE.json').read_text(encoding='utf-8'))
prefixes=('GameCam-WW','GAMECAM_WW','GAMECAM_OWG','GAMECAM_R1','GAMECAM_R2','GAMECAM_R3','GAMECAM_R4','GAMECAM_R5','R6_VP','R6_WW','K7_','GAMECAM_VO_WILDWORLD','GAMECAM_PHASE1','GAMECAM_VISUALIZATION')
outer=('GAMECAM_K6','GAMECAM_WW','GAMECAM-K7','K6-A-')
candidates=[]
for p in BASE.iterdir():
    if p.is_dir() and p.name.startswith(prefixes):candidates.append(('EARLY_THIRD_PERSON_EXPERIMENT',p))
for p in (BASE/'experiments').iterdir():
    if p.is_dir() and p.name.startswith(('GAMECAM_WW','GAMECAM_OPEN_DATA','GAMECAM_GAP')):candidates.append(('EARLY_THIRD_PERSON_EXPERIMENT',p))
for p in WORK.iterdir():
    if p.is_dir() and (p.name.startswith(outer) or p.name=='GAMECAM-VO-FULL-PROJECT-AUDIT-20261109T184515Z'):
        candidates.append(('EARLY_THIRD_PERSON_EXPERIMENT_COPY',p))
for entry in old['targets']:candidates.append((entry['dataset'],Path(entry['path'])))
for base in [BASE,Path('D:/aaa/GameCam-VO-TASK009'),Path('D:/aaa/GameCam-VO-TASK010-A')]:
    for rel in ['docs/history/wildworld_phase1_reports','docs/sources/omniworld']:
        p=base/rel
        if p.exists():candidates.append(('RETIRED_RESEARCH_DOCUMENTS',p))
    if (base/'docs/sources').exists():
        for p in (base/'docs/sources').glob('WildWorld_*'):candidates.append(('RETIRED_RESEARCH_DOCUMENTS',p))
# Exact original early-review files in the project root and Downloads. No
# unrelated installer, credential file, personal file or other project is used.
for parent in [WORK,BASE,Path('C:/Users/Administrator/Downloads')]:
    for p in parent.iterdir():
        if p.is_file() and p.name.startswith(('GAMECAM_K6A_','GAMECAM_WW_','GAMECAM_WW_V5_7_NA_K5_4_1_','V5_7_NA_K2_CHATGPT_REVIEW')):
            candidates.append(('EARLY_REVIEW_COPY',p))

merged=[]
for label,p in sorted(set(candidates),key=lambda pair:len(pair[1].parts)):
    if not p.exists():continue
    actual=p.resolve(strict=True)
    if any(actual.is_relative_to(t[1]) for t in merged):continue
    if actual==BASE or actual==WORK or 'viper' in str(actual).lower():raise RuntimeError('Protected workspace/dataset target')
    if not (actual.is_relative_to(WORK) or actual.parent==Path('C:/Users/Administrator/Downloads')):raise RuntimeError('Outside explicitly searched roots')
    for r in protected:
        if Path(r['path']).is_relative_to(actual):raise RuntimeError('Protected VIPER/current baseline asset intersects '+str(actual))
    merged.append((label,actual))

records=[];targets=[];links=[]
for label,p in merged:
    found=[]
    if p.is_file():found=[p]
    else:
        for here,dirs,files in os.walk(p,followlinks=False):
            reparse_names=set()
            for name in dirs+files:
                q=Path(here,name);s=q.lstat()
                if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    reparse_names.add(name)
                    links.append({'path':str(q),'target':os.readlink(q),'resolved_target':str(q.resolve()),'target_exists_before':q.exists(),'unlink_alias_only':True})
            dirs[:]=[n for n in dirs if n not in reparse_names]
            found.extend(Path(here,n) for n in files)
    part=[]
    for f in found:
        s=f.lstat()
        if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:continue
        r={'path':str(f),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino,'device':s.st_dev,'target':str(p)}
        part.append(r)
    records.extend(part)
    targets.append({'dataset':label,'path':str(p),'kind':'directory' if p.is_dir() else 'file','files':len(part),'bytes':sum(r['bytes'] for r in part)})
if links:
    (OUT/'EXTENDED_REPARSE_POINTS.json').write_text(json.dumps(links,indent=2))
with gzip.open(OUT/'EXTENDED_FILE_IDENTITIES.json.gz','wt',encoding='utf-8') as f:json.dump(records,f,ensure_ascii=False)
plan={'authorization':'User explicitly requests third-person dataset deletion AND deletion of earliest third-person experiments, to prevent stale direction/memory influence.','date':'2026-11-27 Asia/Shanghai','targets':targets,'junction_aliases':links,'shared_junction_target_content_never_included':True,'total_files':len(records),'total_logical_bytes':sum(r['bytes'] for r in records),'volume_before':{v:dict(zip(['total','used','free'],shutil.disk_usage(v))) for v in ['C:/','D:/']},'protected_files':len(protected),'model_runs':0,'VIPER_raw_results_source_shared_weights_envs_protected':True,'sealed_GitHub_history_not_rewritten':True}
(OUT/'EXTENDED_DELETION_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print('EXTENDED PLAN',len(targets),'exact paths',len(records),'files',round(plan['total_logical_bytes']/1024**3,3),'GiB')
for t in sorted(targets,key=lambda r:r['bytes'],reverse=True)[:15]:print(round(t['bytes']/1024**3,3),t['files'],t['path'])
