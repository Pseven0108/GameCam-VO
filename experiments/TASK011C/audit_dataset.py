"""Audit sequence non-overlap before selecting or decoding any new images.

The authoritative full-sequence terminal manifest alone exhausts Validation.
The additional repository manifest census is supporting, not a claim that a
mere filename/reference proves execution. No algorithm performance is used.
"""
from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

import numpy as np

from common import BASE, ROOT, TASK, csvwrite, dump, sha

WEATHERS = ('Day','Sunset','Rain','Snow','Night')
FRESH = BASE/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408'
FULL = FRESH/'results/validation-d1697067dcbde217'
INVENTORY = BASE/'experiments/VIPER_DUAL_BASELINE_FULL_DATASET_STRATIFIED_R1/DATASET_SEQUENCE_INVENTORY.csv'


def eligible(row):
    return (row['rgb_available_in_midpoint'] and row['camera_mapping_exact']
            and row['window_K_max_deviation_px'] < .001
            and row['GT_path_length_native_units'] > .0001
            and not row['used_in_TASK011B'] and not row['used_in_other_comparison'])


def manifest_census():
    roots = [BASE] + [p for p in BASE.parent.glob('GameCam-VO-TASK*') if p != ROOT]
    skip = {'.git','__pycache__','node_modules','envs','external','source','downloads','cache',
            'weights','checkpoints','datasets','build','build_001','local_deps','torch_hub',
            'viper_inputs','rgb','RGB','predictions','derived_maps','risk_maps'}
    paths = []
    expression = re.compile(r'manifest|run[_-]?index|run[_-]?order|selected[_-]?window|validation-complete|execution[_-]?state',re.I)
    for root in roots:
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith('build_')]
            for name in files:
                p = Path(folder)/name
                if p.suffix.lower() not in ('.json','.csv') or not expression.search(name):
                    continue
                if re.search(r'sha256|source_blob|allowlist|publication|credential|token|known_hosts',name,re.I):
                    continue
                if p.stat().st_size > 20*1024**2:
                    paths.append(dict(path=str(p),bytes=p.stat().st_size,status='SIZE_LIMIT_NOT_PARSED',validation_references=''))
                    continue
                try:
                    text = p.read_text(encoding='utf-8-sig')
                    refs = sorted(set(re.findall(r'\bval_\d{3}(?=[_\W]|$)',text)))
                    paths.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),
                                      status='REFERENCE_CENSUS_ONLY_NOT_EXECUTION_PROOF',
                                      validation_references=';'.join(refs)))
                except (UnicodeError,OSError) as exc:
                    paths.append(dict(path=str(p),bytes=p.stat().st_size,status=type(exc).__name__,validation_references=''))
    return sorted(paths,key=lambda x:x['path'])


def main():
    out = TASK/'data_audit_final'
    out.mkdir(exist_ok=False)
    inventory = list(csv.DictReader(INVENTORY.open(encoding='utf-8-sig')))
    rows = [r for r in inventory if r['split'] == 'val']
    if len(rows) != 47 or len({r['sequence_id'] for r in rows}) != 47:
        raise RuntimeError('Validation inventory identity changed')
    bpath = ROOT/'experiments/TASK011B/configs/VIPER_WINDOW_MANIFEST.csv'
    b_rows = list(csv.DictReader(bpath.open()))
    b_used = {r['sequence'] for r in b_rows}
    history_path = FULL/'evidence/validation-complete.json'
    history = json.loads(history_path.read_text())
    if history['planned'] != 94 or history['terminal'] != 94 or len(history['results']) != 94:
        raise RuntimeError('Historical terminal manifest is incomplete')
    historical = []
    used = set()
    for i, record in enumerate(history['results']):
        case, model = record['case'],record['model']
        if not re.fullmatch(r'val_\d{3}',case) or model not in ('slam','wild'):
            raise RuntimeError('Historical split/model identity is ambiguous')
        # Source identity/status are checked against the independent per-attempt
        # receipt; numeric scores are intentionally not read for selection.
        path = FULL/record['attempt']/'attempt.json'
        attempt = json.loads(path.read_text())
        if (attempt['case'],attempt['model'],attempt['status']) != (case,model,record['status']):
            raise RuntimeError('Historical aggregate and individual attempt disagree')
        if record['status'] not in ('COMPLETE','GPU_OOM','BUFFER_CAPACITY'):
            raise RuntimeError('Unclassified historical terminal status')
        if record['status'] != 'COMPLETE' and int(record['last_progress']['done']) <= 0:
            raise RuntimeError('Cannot establish actual execution of failed attempt')
        used.add(case)
        historical.append(dict(sequence=case,model=model,status=record['status'],stride=record['stride'],
                               aggregate_json_pointer='/results/'+str(i),aggregate_sha256=sha(history_path),
                               attempt_path=str(path),attempt_sha256=sha(path),
                               used_for_exclusion=True,performance_used_for_selection=False))
    if used != {'val_'+r['sequence_id'] for r in rows}:
        raise RuntimeError('Historical/current Validation source identities differ')
    csvwrite(out/'HISTORICAL_EXECUTION_EVIDENCE.csv',historical)
    census = manifest_census()
    csvwrite(out/'REPOSITORY_MANIFEST_CENSUS.csv',census)
    # Read only original ZIP central directories. No RGB extraction or JPEG
    # decoding is useful when every candidate is already excluded by sequence.
    archives = BASE/'downloads/VIPER_RGB_JPG_ORIGINALS_20261119/archives'
    members = set()
    archive_rows = []
    for path in sorted(archives.glob('val_img*.zip')):
        with zipfile.ZipFile(path) as z:
            # Common directory entries are present in multiple shards. Only
            # JPEG file identities are relevant to the exact-frame census.
            names = [i.filename for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith('.jpg')]
        duplicate = members.intersection(names)
        if duplicate:
            raise RuntimeError('Duplicate validation JPEG archive identity')
        members.update(names)
        archive_rows.append(dict(path=str(path),bytes=path.stat().st_size,members=len(names),
                                 operation='CENTRAL_DIRECTORY_ONLY_NO_DECODE'))
    candidates = []
    for record in sorted(rows,key=lambda r:int(r['sequence_id'])):
        case = 'val_'+record['sequence_id']
        start = int(record['min_frame'])+(int(record['rgb_valid'])-64)//2
        ids = np.arange(start,start+64)
        expected = [f"val/img/{record['sequence_id']}/{record['sequence_id']}_{x:05d}.jpg" for x in ids]
        gt_path = FRESH/'offline_gt'/(case+'.npz')
        with np.load(gt_path,allow_pickle=False) as z:
            by_id = {int(v):i for i,v in enumerate(z['rgb_ids'])}
            if len(by_id) != len(z['rgb_ids']) or any(int(x) not in by_id for x in ids):
                raise RuntimeError('GT frame identity incomplete: '+case)
            ix = [by_id[int(x)] for x in ids]
            camera = z['camera_ids'][ix]
            gt = z['gt_c2w'][ix]
            k = z['raw_intrinsics'][ix]
        if not np.isfinite(gt).all() or not np.isfinite(k).all():
            raise RuntimeError('Nonfinite GT/K in historical offline cache')
        path_length = float(np.linalg.norm(np.diff(gt[:,:3,3],axis=0),axis=1).sum())
        result = dict(sequence=case,environment=record['environment'],rgb_start=start,rgb_end=start+63,
                      midpoint_rule='min_frame + floor((rgb_valid-64)/2)',frame_count=64,
                      rgb_available_in_midpoint=all(p in members for p in expected),
                      camera_mapping_exact=bool(np.array_equal(camera,ids-1)),
                      window_K_max_deviation_px=float(np.max(np.abs(k-k[0]))),
                      GT_path_length_native_units=path_length,GT_motion_eligible=path_length>.0001,
                      gt_source_sha256=sha(gt_path),used_in_TASK011B=case in b_used,
                      used_in_other_comparison=case in used,
                      past_stride4_counts_as_sequence_exposure=True)
        result['eligible'] = eligible(result)
        reasons = []
        if result['used_in_TASK011B']: reasons.append('TASK011B_SOURCE_SEQUENCE')
        if result['used_in_other_comparison']: reasons.append('PRIOR_DUAL_BASELINE_FULLSEQ_SOURCE')
        if not result['GT_motion_eligible']: reasons.append('GT_PATH_NOT_ABOVE_0.0001')
        if result['window_K_max_deviation_px'] >= .001: reasons.append('WINDOW_VARIABLE_K')
        if not result['rgb_available_in_midpoint']: reasons.append('CENTRAL_DIRECTORY_MISSING_RGB')
        if not result['camera_mapping_exact']: reasons.append('CAMERA_MAPPING')
        result['exclusion_reasons'] = ';'.join(reasons)
        candidates.append(result)
    csvwrite(out/'VALIDATION_SEQUENCE_ADMISSION.csv',candidates)
    summary = []
    for weather in WEATHERS:
        own = [r for r in candidates if r['environment'] == weather]
        summary.append(dict(environment=weather,total_sequences=len(own),
            TASK011B_used=sum(r['used_in_TASK011B'] for r in own),
            remaining_after_TASK011B_only=sum(not r['used_in_TASK011B'] for r in own),
            historical_exposure=sum(r['used_in_other_comparison'] for r in own),
            eligible_after_all_rules=sum(r['eligible'] for r in own),required=4))
    csvwrite(out/'WEATHER_AVAILABILITY.csv',summary)
    if any(r['eligible'] for r in candidates):
        raise RuntimeError('Unexpected eligible data: audit decision requires reinspection before freezing')
    # Preserve source records in the reviewable task evidence; these contain
    # metadata only, with no raw camera matrices, images or model weights.
    shutil.copy2(INVENTORY,out/'SOURCE_DATASET_SEQUENCE_INVENTORY.csv')
    shutil.copy2(history_path,out/'SOURCE_VALIDATION_TERMINAL_MANIFEST.json')
    csvwrite(out/'SOURCE_ATTEMPT_IDENTITIES.csv',historical)
    dump(out/'ARCHIVE_DIRECTORY_CHECK.json',dict(archives=archive_rows,
        JPEGs_extracted=0,JPEGs_decoded=0,central_directory_presence_not_CRC_or_decode_certificate=True))
    dump(out/'DATA_ADMISSION_DECISION.json',dict(status='BLOCKED_NO_UNSEEN_VALIDATION_SOURCE_SEQUENCES',
        validation_sequences=47,historically_executed_sequences=47,
        historical_model_terminal_records=94,historical_statuses=dict(Counter(x['status'] for x in historical)),
        TASK011B_sequences=20,eligible_sequences=0,selected_windows=0,selection_frozen=False,
        GPU_experiments_started=0,mean_geometry_protocol_not_relaxed=True,
        further_manifest_census_files=len(census),all_weather_groups_sufficient=False,
        source_inventory_sha256=sha(INVENTORY),TASK011B_manifest_sha256=sha(bpath),
        terminal_manifest_sha256=sha(history_path),
        second_independent_blocker='Even ignoring older experiments, Rain has only 3 sources after TASK011B; need 4',
        statistical_decision='INCONCLUSIVE',
        requires_user_decision_before_any_sampling_protocol_change=True))
    csvwrite(out/'GPU_EXECUTION_MANIFEST.csv',[],fields=['window','sequence','environment','seed','arm','execution_order'])
    print(json.dumps(dict(status='DATA_ADMISSION_BLOCKED',eligible_sequences=0,weather=summary,
        manifest_census_files=len(census),GPU_runs=0),ensure_ascii=False))


if __name__ == '__main__':
    main()
