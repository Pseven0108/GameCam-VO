"""Identify only stale early third-person status/config/result entries."""
from pathlib import Path
import hashlib,json,os,stat
OUT=Path(__file__).resolve().parent
roots=[Path('D:/aaa/GameCam-VO'),Path('D:/aaa/GameCam-VO-TASK009'),Path('D:/aaa/GameCam-VO-TASK010-A')]
names=['00_project_status.md','01_dataset_validation.md','02_orb_essential.md','03_orb_slam3.md','04_droid_slam.md','05_monst3r.md','06_vggt.md','07_megasam.md','08_baseline_comparison.md','09_dynamic_mask_ablation.md','10_research_direction_decision.md','baseline_comparison.md','data_acquisition_plan.md','dataset_access_status.json','E0_data_validation_report.md','E5_dynamic_mask_ablation.md','omniworld_baseline.md','omniworld_validation.md','project_status.json','public_experiment_status.json','research_direction_decision.md']
pointers=['OWG_MAPPING_ACTIVE_WORKSPACE.txt','PHASE1_PHASE2_ACTIVE_WORKSPACE.txt','R3_120R_ACTIVE_WORKSPACE.txt','R3_45_ACTIVE_WORKSPACE.txt','R4_ACTIVE_WORKSPACE.txt','R5A_ACTIVE_WORKSPACE.txt','R5B_ACTIVE_WORKSPACE.txt','R5C_ACTIVE_WORKSPACE.txt']
protected=json.loads((OUT/'PROTECTED_BEFORE.json').read_text(encoding='utf-8'))
targets=[]
for root in roots:
    items=[root/'reports'/n for n in names]+[root/n for n in pointers]+[root/'configs/datasets'/n for n in ['wildworld.yaml','omniworld_game.yaml']]
    items += [root/'results'/n for n in ['E0','E1','E2','E3','E4','E5','E0_OMNI','E1A_OMNI','E1B_OMNI','E5_OMNI','comparison/omniworld_game']]
    items += [root/'logs/acquisition_omni']
    for p in items:
        if not p.exists():continue
        if any(Path(r['path']).is_relative_to(p) for r in protected):raise RuntimeError('Protected overlap')
        if not p.resolve().is_relative_to(root):raise RuntimeError('Path boundary mismatch')
        files=[p] if p.is_file() else [Path(here,n) for here,dirs,names_ in os.walk(p,followlinks=False) for n in names_]
        records=[]
        for f in files:
            s=f.lstat()
            if s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:raise RuntimeError('Unexpected link')
            records.append({'path':str(f),'bytes':s.st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
        targets.append({'path':str(p),'kind':'directory' if p.is_dir() else 'file','files':records,'bytes':sum(r['bytes'] for r in records)})
(OUT/'SUPPLEMENTARY_PLAN.json').write_text(json.dumps({'targets':targets,'protected_overlap':False},ensure_ascii=False,indent=2),encoding='utf-8')
print('Retired entry targets',len(targets),'files',sum(len(t['files']) for t in targets),'bytes',sum(t['bytes'] for t in targets))
