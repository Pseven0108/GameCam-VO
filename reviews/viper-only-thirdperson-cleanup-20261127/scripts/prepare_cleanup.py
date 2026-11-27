"""Create explicit, disjoint data-only deletion and protection manifests."""
from pathlib import Path
import csv, hashlib, io, json, os, shutil, stat

OUT=Path(__file__).resolve().parent
BASE=Path('D:/aaa/GameCam-VO')
TASK=Path('D:/aaa/GameCam-VO-TASK010-A/experiments/TASK010-A')
relative=[
('WildWorld','GameCam-WW-V5/inputs/depth'),
('WildWorld','GameCam-WW-V5/inputs/hf_download'),
('WildWorld','GameCam-WW-V5_4/inputs'),
('WildWorld','GameCam-WW-V5_5/data'),
('WildWorld','GameCam-WW-V5_6/data'),
('WildWorld','GameCam-WW-V5_7-NA-K3/inputs'),
('WildWorld','GameCam-WW-V5_7-NA-K4/inputs'),
('WildWorld','experiments/GAMECAM_WW_00/03_samples'),
('WildWorld','experiments/GAMECAM_WW_01/02_frame_extraction'),
('WildWorld','experiments/GAMECAM_WW_04A/data'),
('WildWorld','experiments/GAMECAM_WW_04B_D2_GEOM_01/data'),
('DigiDogs','experiments/GAMECAM_OPEN_DATA_01/02_download/DigiDogs2024_full.tar.gz'),
('DigiDogs','experiments/GAMECAM_OPEN_DATA_01/02_download/digidogs_transfer_chunks'),
('DigiDogs','experiments/GAMECAM_OPEN_DATA_01/03_samples/digidogs_sequence'),
('DigiDogs','experiments/GAMECAM_OPEN_DATA_01/03_samples/digidogs_static_sequence'),
('DigiDogs','experiments/GAMECAM_GAP_01/01_dataset_audit/rgb_cache'),
('DigiDogs','experiments/GAMECAM_GAP_01/01_dataset_audit/mask_cache'),
('DigiDogs','experiments/GAMECAM_GAP_01/01_dataset_audit/native_features'),
('GameVerse','experiments/GAMECAM_OPEN_DATA_01/03_samples/gameverse_sequence'),
('OmniWorld-Game','data/omniworld_game'),
('OmniWorld-Game','R6_VP1_OTHERS_FULL_DOWNLOAD_20261115/02_ARCHIVES'),
('OmniWorld-Game','R6_VP1_OTHERS_FULL_DOWNLOAD_20261115/03_CAPTIONS_ONLY'),
('OmniWorld-Game','R6_VP2B_RGB_VISUAL_VALIDATION_20261115/01_RGB_ARCHIVES'),
('OmniWorld-Game','R6_VP2B_RGB_VISUAL_VALIDATION_20261115/03_RGB_PNG'),
('OmniWorld-Game','R6_VP2B_RGB_VISUAL_VALIDATION_20261115/VP2B_1_COLOR_ROOT_AMENDMENT_20261115/02_RGB_PNG'),
('OmniWorld-Game','GAMECAM_OWG_CAPTION_PILOT_20261115/02_ORIGINAL_ARCHIVES'),
]
targets=[(label,BASE/rel) for label,rel in relative]
targets.append(('WildWorld',TASK/'private/datasets/wildworld_thirdperson_qual'))
for p in BASE.glob('GameCam-WW-*/derived'):
    # Derived arrays are retained as historical result evidence, not active inputs.
    pass

def identity(p):
    s=p.lstat()
    if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:raise RuntimeError('Reparse point in deletion/protection target: '+str(p))
    return {'path':str(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino,'device':s.st_dev}

def files_under(p):
    identity(p)
    if p.is_file():return [p]
    found=[]
    for here,dirs,files in os.walk(p,followlinks=False):
        for name in dirs:identity(Path(here,name))
        for name in files:found.append(Path(here,name))
    return found

entries=[];all_targets=[];missing=[]
blocked_suffix={'.py','.pyc','.sh','.so','.pyd','.whl','.pth','.pt','.safetensors','.exe','.dll'}
for label,p in targets:
    if not p.exists():missing.append(str(p));continue
    actual=p.resolve(strict=True)
    if not actual.is_relative_to(Path('D:/aaa')) or actual==Path('D:/aaa') or any(x in str(actual).lower() for x in ('viper','/reviews/','\\reviews\\')):
        raise RuntimeError('Deletion path escaped exact project dataset scope: '+str(actual))
    for q in all_targets:
        if actual.is_relative_to(Path(q['path'])) or Path(q['path']).is_relative_to(actual):raise RuntimeError('Overlapping targets')
    files=files_under(actual)
    for f in files:
        if f.suffix.lower() in blocked_suffix:raise RuntimeError('Potential code/model in dataset target: '+str(f))
    records=[dict(identity(f),dataset=label,target=str(actual)) for f in files]
    entries.extend(records)
    all_targets.append({'dataset':label,'path':str(actual),'kind':'directory' if actual.is_dir() else 'file','files':len(records),'bytes':sum(r['bytes'] for r in records)})

# Exact-path VIPER archive metadata, all latest experiment evidence except the
# requested 32-image WildWorld input, and representative original VIPER GT/RGB.
protected=set()
discovery=json.loads((OUT/'LOCAL_DISCOVERY.json').read_text(encoding='utf-8'))
for record in discovery['archives']:
    if 'viper' in record['path'].lower():protected.add(Path(record['path']))
for base in [TASK/'outputs/droid',TASK/'private/datasets',TASK/'09_reproducibility',TASK/'08_reports',BASE/'baselines/droid_w']:
    if base.exists():
        for here,dirs,files in os.walk(base,followlinks=False):
            dirs[:]=[n for n in dirs if n not in {'.git','__pycache__'}]
            for name in files:
                p=Path(here,name)
                if 'wildworld_thirdperson_qual' not in str(p):protected.add(p)
for p in protected:
    if any(p.is_relative_to(Path(t['path'])) for t in all_targets):raise RuntimeError('Protected path intersects deletion list: '+str(p))
preservation=[]
for p in sorted(protected):
    r=identity(p)
    # Main raw VIPER shards use metadata protection; small files get byte hashes.
    if r['bytes']<=16*1024**2:r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    preservation.append(r)
(OUT/'PROTECTED_BEFORE.json').write_text(json.dumps(preservation,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'DELETE_FILE_IDENTITIES.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
plan={'authorization':'User requests deletion of third-person dataset branches, retaining VIPER','date':'2026-11-27 Asia/Shanghai','allowed_workspace':'D:/aaa','targets':all_targets,'missing_paths':missing,'total_files':len(entries),'total_logical_bytes':sum(r['bytes'] for r in entries),'data_volume_before':dict(zip(['total','used','free'],shutil.disk_usage('D:/'))),'protected_files':len(preservation),'historical_reports_code_weights_results_not_deletion_targets':True}
(OUT/'LOCAL_DELETION_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print('EXACT DATA TARGETS')
for r in all_targets:print(r['dataset'],round(r['bytes']/1024**3,3),r['files'],r['path'])
print('TOTAL',len(all_targets),'paths',len(entries),'files',round(plan['total_logical_bytes']/1024**3,3),'GiB','PROTECTED',len(preservation))
