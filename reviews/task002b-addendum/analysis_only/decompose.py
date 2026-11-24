"""Partition the frozen R2 metrics without rerunning models, decoding RGB, or refitting subsets."""
import csv
import json
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from zipfile import ZipFile

from metrics import (OUT,PARENT,CLASSES,MODELS,PAIR_TYPES,THIRDS,CASE,FLOOR,
                     align_once,close,fmt,load_export,np,pair_pack,pair_stats,stats)
from case_data import adjacent_and_direct,case_records,frame_rows
from audit_common import (COMMITS,EVAL_SHA,OFFSETS,R1,R2,ZIP,ZIP_SHA,digest,exact_member,load_contract,
                          read_csv,read_json,require,sha,verify_package)
from audit_motion import gt_checks,prepare_evaluator

META=['segment','sequence','environment','calibration_branch']
CHECKED=('valid_count','expected_count','invalid_or_missing_count','translation_sse','rotation_sse',
         'ratio_count','screened_ratio_count','screened_compression_lt_half_count')


def write_csv(name, rows):
    require(bool(rows),f'no rows: {name}')
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader(); w.writerows(rows)


def write_json(name, obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def prior(name, locks, protected):
    p=PARENT/name
    h=digest(p)
    require(name in locks and locks[name]['sha256']==h and locks[name]['bytes']==p.stat().st_size,
            f'parent manifest failure: {name}')
    protected[p]=h
    return p


def case_reproduce(cases, history):
    for row in cases:
        old=history[(row['model'],row['first_rgb'],row['last_rgb'])]
        for field,prev in (('scaled_displacement_ratio','scaled_to_gt_ratio'),
                           ('translation_rpe_game_units','official_rpe_convention_translation_one_pair'),
                           ('rotation_rpe_deg','relative_camera_rotation_error_deg')):
            close(row[field],old[prev],f'val_007 case {field}')
        flags=[x == 'True' for x in (old['first_is_keyframe'],old['last_is_keyframe'])]
        require(row['endpoint_type']==PAIR_TYPES[2*int(not flags[0])+int(not flags[1])],'case keyframe status differs')


def phases(n):
    phase=np.empty(n,int)
    for j,chunk in enumerate(np.array_split(np.arange(n),3)):
        phase[chunk]=j
    return phase


def frame_summaries(meta, model, d, peer, sl, wi, phase):
    allf=np.ones(len(sl),bool)
    for population,groups in (
        ('OWN',zip((*CLASSES,'ALL'),(d['source'],~d['source'],allf))),
        ('MATCHED',zip((*CLASSES,'ALL'),(sl&wi,~sl&~wi,allf))),
        ('SLAM_KF_WILD_FILLED',[('DISAGREE',sl&~wi)]),('SLAM_FILLED_WILD_KF',[('DISAGREE',~sl&wi)])):
        for label,selected in groups:
            for i,part in enumerate(('all',*THIRDS)):
                pick=selected if i==0 else selected&(phase==i-1)
                ok=pick&d['valid']
                if population!='OWN': ok&=peer['valid']
                yield dict(**meta,model=model,trajectory_sha256=d['trajectory_sha256'],population=population,
                           frame_type=label,temporal_third=part,**stats(d['translation'][ok]**2,d['angle'][ok],pick.sum()))


def categorize_pairs(ev,meta,ids,truth,phase,models,metrics,detail,pairs,recon,case_pairs,index):
    require(np.all(np.diff(ids)==1),'unexpected gap in frozen manifest')
    for off in (*OFFSETS,*((16,52) if meta['segment']==CASE else ())):
        i=np.arange(max(0,len(ids)-off)); j=i+off
        gt_step=np.linalg.norm(ev.rel_pose(truth[:,:3,3],truth[:,:3,:3],i,j)[0],axis=1)
        moving=gt_step>FLOOR
        screen=float(.5*np.median(gt_step[moving])) if moving.any() else None
        eligible=moving & (gt_step>=screen) if screen is not None else moving
        gtbin=np.full(len(i),-1,int)
        if moving.any(): gtbin[moving]=np.searchsorted(np.quantile(gt_step[moving],[1/3,2/3]),gt_step[moving],side='left')
        (sc,sv,sr),(wc,wv,wr)=(pair_pack(ev,d,ids,truth,i,j,off) for d in models.values())
        if off not in OFFSETS:
            for k in range(len(i)):
                case_pairs.append(dict(**meta,offset=off,first_rgb=int(ids[i[k]]),last_rgb=int(ids[j[k]]),
                    gt_step_game_units=fmt(gt_step[k]),gt_screen_pass=bool(eligible[k]),slam_type=PAIR_TYPES[sc[k]],wild_type=PAIR_TYPES[wc[k]],
                    slam_ratio=fmt(sr[k,3]),wild_ratio=fmt(wr[k,3]),slam_trans_error=fmt(np.sqrt(sr[k,0])),
                    wild_trans_error=fmt(np.sqrt(wr[k,0])),slam_rot_deg=fmt(sr[k,1]),wild_rot_deg=fmt(wr[k,1]),
                    slam_trajectory_sha256=models[MODELS[0]]['trajectory_sha256'],wild_trajectory_sha256=models[MODELS[1]]['trajectory_sha256']))
            continue
        for name,d,cls,ok,v in ((MODELS[0],models[MODELS[0]],sc,sv,sr),(MODELS[1],models[MODELS[1]],wc,wv,wr)):
            total=pair_stats(v,ok,np.ones(len(i),bool),eligible)
            own=[pair_stats(v,ok,cls==k,eligible) for k in range(4)]
            old=metrics[(meta['segment'],name,off)]
            for fld in CHECKED:
                close(sum(x[fld] for x in own),total[fld],f'endpoint partition {fld}',atol=1e-9,rtol=1e-12)
            for fld,prev in (('valid_count','valid_pair_count'),('expected_count','expected_pair_count'),
                             ('invalid_or_missing_count','invalid_pair_count'),('translation_rmse','translation_rpe'),('rotation_rmse_deg','rotation_rpe')):
                close(total[fld],old[prev],f'{meta["segment"]} {name} +{off} {fld}')
            recon.append(dict(**meta,model=name,offset=off,**total,
                partition_translation_sse=sum(x['translation_sse'] for x in own),partition_rotation_sse=sum(x['rotation_sse'] for x in own),
                translation_rmse_parent=float(old['translation_rpe']) if old['translation_rpe'] else None,
                rotation_rmse_parent=float(old['rotation_rpe']) if old['rotation_rpe'] else None))
            common=dict(**meta,model=name,trajectory_sha256=d['trajectory_sha256'],offset=off,nominal_seconds=off/15,
                        gt_step_screen_game_units=screen)
            pairs.extend(dict(**common,population='OWN',endpoint_type=PAIR_TYPES[k],**row) for k,row in enumerate(own))
            for a in range(4):
                for b in range(4):
                    pairs.append(dict(**common,population='MATCHED_CLASS_GRID',endpoint_type=PAIR_TYPES[a if name==MODELS[0] else b],
                        slam_type=PAIR_TYPES[a],wild_type=PAIR_TYPES[b],**pair_stats(v,sv&wv,(sc==a)&(wc==b),eligible)))
        mid=phase[(i+j)//2]
        for k in range(len(i)):
            detail.writerow([index,off,int(ids[i[k]]),fmt(gt_step[k]),THIRDS[mid[k]],int(gtbin[k]),int(eligible[k]),
                int(sc[k]),int(wc[k]),'VALID' if sv[k] else 'INVALID_OR_MISSING_INTERVAL',
                'VALID' if wv[k] else 'INVALID_OR_MISSING_INTERVAL',fmt(sr[k,0]),fmt(wr[k,0]),fmt(sr[k,1]),fmt(wr[k,1]),fmt(sr[k,3]),fmt(wr[k,3])])


def validate_ids(plan, doc, ids):
    require(doc['id']==plan['id'] and doc['sequence']==plan['sequence'] and doc['branch']==plan['branch'] and
            doc['stride']==1 and doc['out_wh']==[640,360] and doc['fps_nominal']==15 and
            np.array_equal(ids,[x['rgb_id'] for x in doc['frames']]) and len(ids)==int(plan['frames']),
            f'manifest mapping {plan["id"]}')


def run():
    start=time.monotonic(); count=verify_package()
    protected={ZIP:ZIP_SHA,PARENT/'FILE_SHA256_MANIFEST.json':digest(PARENT/'FILE_SHA256_MANIFEST.json')}
    locks={r['path']:r for r in read_json(PARENT/'FILE_SHA256_MANIFEST.json')['files']}
    for name in ('analysis_only/audit_common.py','analysis_only/audit_motion.py','R2_STATISTICAL_CONTRACT.json',
                 'TASK002B_FROZEN_EVIDENCE_AUDIT.json','TASK002B_SOURCE_EVIDENCE_INDEX.json'):
        prior(name,locks,protected)
    metric={(r['segment'],r['model'],int(r['offset'])):r for r in
            read_csv(prior('R2_RPE_PER_SEGMENT.csv',locks,protected)) if r['scope']=='full'}
    history={(r['segment'],r['model']):r for r in read_csv(prior('R2_TRAJECTORY_AND_GT_INTEGRITY.csv',locks,protected))}
    val_history={(r['model'],int(r['first_rgb']),int(r['last_rgb'])):r for r in
                 read_csv(prior('R2_VAL007_LOCAL_INTERVAL_VERIFICATION.csv',locks,protected))}
    names=('KEYFRAME_ID_AUDIT.csv','POSE_ERROR_BY_SEGMENT_AND_TIME.csv','RPE_BY_ENDPOINT_TYPE.csv',
           'KEYFRAME_CONSECUTIVE_RPE.csv','DIRECT_FINAL_BA_ANCHOR_COMPARISON.csv','RPE_PARTITION_RECONCILIATION.csv',
           'RPE_PAIR_SEGMENT_INDEX.csv','evidence/R2_STAGE_AND_ALIGNMENT_INDEX.csv','VAL007_CASE_INTERVALS.csv',
           'VAL007_SAME_OFFSET_PAIRS.csv','VAL007_ANCHOR_INTERVALS.csv','VAL007_FRAME_SERIES.csv')
    id_audit,frame_summary,pairs,adjacent,direct,recon,pair_index,stages,cases,case_pairs,anchors,series=lists=[[] for _ in names]
    all_frames=Counter(); all_keys=Counter(); branch_count=Counter(); branch_frames=Counter()
    with ZipFile(ZIP) as z, ExitStack() as ctx:
        contract,plans=load_contract(z)
        ev,loaders=prepare_evaluator(z)
        require(len(metric)==len(plans)*len(MODELS)*len(OFFSETS) and len(history)==len(plans)*len(MODELS),'parent coverage')
        print(f'CRC and lock: {count} ZIP members, {len(plans)} segments',flush=True)
        for p in ('pipeline/offline_evaluation.py','pipeline/validate_smoke.py','pipeline/transfer_common.py',
                  'pipeline/run_original.py','VIPER_R2_FROZEN_VAL92_MANIFEST.csv','evidence/R1_PRESERVATION_AND_SCORE_CHECK.json'):
            protected[R2/p]=sha(exact_member(z,p))
        for name in ('PROTOCOL_LOCK.json','VIPER_R2_PROTOCOL_LOCK.json'):
            protected[R2/name]=sha(exact_member(z,'PROTOCOL_LOCK.json',R2/name))
        gt_hashes=json.loads(exact_member(z,'evidence/R1_PRESERVATION_AND_SCORE_CHECK.json'))['gt_file_sha256']
        history_runner=R1/'pipeline/run_segment.py'
        index=read_json(PARENT/'TASK002B_SOURCE_EVIDENCE_INDEX.json')
        require(digest(history_runner)=='428ca308f9df4d9375251f463fb560673c323aa9e62c9a2fcc98ffa6e99180e6',
                'R1 runner drift from parent sealed source check')
        protected[history_runner]=digest(history_runner)
        cols=META+['model','rgb_id','camera_id','local_index','trajectory_sha256','expected_source_type','frame_type',
                   'pose_status','pose_origin','other_model_source_type','other_model_pose_status','temporal_third',
                   'align_scale','trajectory_row_0based']
        writers={}
        for label,name in [('ROSTER','FRAME_TYPE_MANIFEST.csv'),('KEYFRAME','KEYFRAME_POSE_ERROR.csv'),('FILLED_FRAME','FILLED_FRAME_POSE_ERROR.csv')]:
            extra=[] if label=='ROSTER' else ['translation_error_game_units','rotation_error_deg']
            writers[label]=csv.DictWriter(ctx.enter_context((OUT/name).open('w',encoding='utf-8-sig',newline='')),
                                           cols+extra,extrasaction='ignore')
            writers[label].writeheader()
        detail=csv.writer(ctx.enter_context((OUT/'RPE_PAIR_DETAIL.csv').open('w',encoding='utf-8-sig',newline='')))
        detail.writerow(['segment_index','offset','start_rgb','gt_step','temporal_third','gt_motion_bin','gt_screen_pass',
                         'slam_type','wild_type','slam_interval_status','wild_interval_status','slam_trans_error_sq',
                         'wild_trans_error_sq','slam_rot_deg','wild_rot_deg','slam_scaled_ratio','wild_scaled_ratio'])
        for ix,plan in enumerate(plans):
            sid=plan['id']; branch=plan['branch']
            meta=dict(segment=sid,sequence=plan['sequence'],environment=plan['environment'],calibration_branch=branch)
            ids=np.arange(int(plan['first']),int(plan['last'])+1)
            member=f'manifests/{sid}.json'; mb=exact_member(z,member)
            require(sha(mb)==plan['input_manifest_sha256'],'segment manifest hash mismatch')
            protected[R2/member]=sha(mb); validate_ids(plan,json.loads(mb),ids)
            truth,gt=gt_checks(plan,gt_hashes,loaders,ids)
            protected[Path(gt['gt_path'])]=gt['gt_sha256']
            phase=phases(len(ids)); branch_count[branch]+=1; branch_frames[branch]+=len(ids)
            models={m:load_export(z,plan,m,ids,protected) for m in MODELS}
            sl,wi=(models[m]['source'] for m in MODELS)
            pair_index.append(dict(segment_index=ix,**meta,first_rgb=int(ids[0]),last_rgb=int(ids[-1]),gt_sha256=gt['gt_sha256'],
                slam_trajectory_sha256=models[MODELS[0]]['trajectory_sha256'],wild_trajectory_sha256=models[MODELS[1]]['trajectory_sha256']))
            for name,d in models.items():
                peer=models[MODELS[1] if name==MODELS[0] else MODELS[0]]; old=history[(sid,name)]
                require(d['trajectory_sha256']==old['trajectory_sha256'] and d['valid'].sum()==int(old['valid_pose_count']) and
                        d['source'].sum()==int(old['keyframe_count']),f'parent trajectory mismatch: {sid} {name}')
                align_once(ev,d,truth,metric[(sid,name,1)])
                all_keys[name]+=int(d['source'].sum()); all_frames[name]+=int(d['valid'].sum())
                nm=dict(**meta,model=name,trajectory_sha256=d['trajectory_sha256'])
                id_audit.append(dict(**nm,trajectory_member=d['member'],verified_receipts=d['verified_receipts'],export_schema=d['export_schema'],
                    input_frames=len(ids),exported_count=int((d['slot']>=0).sum()),valid_count=int(d['valid'].sum()),
                    missing_count=int((d['status']=='MISSING').sum()),invalid_count=int((d['status']=='INVALID').sum()),
                    keyframe_count=len(d['keys']),keyframe_to_exported_fraction=len(d['keys'])/int((d['slot']>=0).sum()),
                    filled_frame_count=int((~d['source']).sum()),shared_kf=int((sl&wi).sum()),both_filled=int((~sl&~wi).sum()),
                    slam_kf_only=int((sl&~wi).sum()),wild_kf_only=int((~sl&wi).sum()),same_kf_set=bool(np.array_equal(sl,wi)),
                    direct_ba_archive_array_count=0 if d['direct'] is None else len(d['direct']),
                    keyframe_export_origin='FINAL_BA_ANCHOR_REINSERTED' if name==MODELS[1] else 'FILLER_OUTPUT',
                    recorded_pre_final_ba_anchor_pose_count=0))
                stages.append(dict(**nm,**{f:d[f] for f in ('final_ba','pre_final_diagnostic','filler_use_dino_features',
                    'filler_uncertainty_activate','filler_bidirectional_u')}, alignment_scale=d['scale'],alignment_rank=d['rank'],
                    alignment_rotation=d['r'].tolist(),alignment_translation=d['t'].tolist()))
                for row in frame_rows(meta,name,d,peer,ids,phase):
                    writers['ROSTER'].writerow(row); writers[row['expected_source_type']].writerow(row)
                frame_summary.extend(frame_summaries(meta,name,d,peer,sl,wi,phase))
                a,b=adjacent_and_direct(ev,meta,name,d,ids,truth,phase); adjacent.extend(a); direct.extend(b)
            if sid==CASE:
                for name,d in models.items():
                    a,b,c=case_records(ev,meta,ids,truth,name,d,models); cases.extend(a); series.extend(b); anchors.extend(c)
                    case_reproduce(a,val_history)
            categorize_pairs(ev,meta,ids,truth,phase,models,metric,detail,pairs,recon,case_pairs,ix)
            if (ix+1)%16==0 or ix+1==len(plans): print(f'Segment {ix+1}/{len(plans)} complete',flush=True)
    require(all_keys==dict(zip(MODELS,(8042,12568))) and all_frames==dict.fromkeys(MODELS,49815),'parent totals differ')
    for name,rows in zip(names,lists): write_csv(name,rows)
    preservation=[dict(path=str(p),sha256=h,bytes=p.stat().st_size,unchanged=digest(p)==h) for p,h in sorted(protected.items())]
    require(all(x['unchanged'] for x in preservation),'historical input changed')
    write_csv('evidence/ORIGINAL_EVIDENCE_PRESERVATION.csv',preservation)
    write_json('evidence/NUMERICAL_VERIFICATION.json',dict(status='PASS',protocol=contract['protocol'],stride=1,
        source_zip_sha256=ZIP_SHA,source_zip_crc='PASS',source_zip_members=count,source_evaluator_sha256=EVAL_SHA,
        source_commits=COMMITS,protected_historical_files=len(preservation),total_poses=all_frames,total_keyframes=all_keys,
        group_segment_counts=branch_count,group_expected_frames_per_model=branch_frames,
        compared_parent_full_rpe_cells=len(recon)*5,endpoint_partitions=len(recon),endpoint_partition_checks=len(recon)*len(CHECKED),
        reproduced_case_interval_rows=len(cases),
        max_parent_translation_difference=max(abs(r['translation_rmse']-r['translation_rmse_parent']) for r in recon if r['valid_count']),
        max_parent_rotation_difference=max(abs(r['rotation_rmse_deg']-r['rotation_rmse_parent']) for r in recon if r['valid_count']),
        numpy=np.__version__,elapsed_seconds=time.monotonic()-start,raw_rgb_read_bytes=0))
    print(f'PASS: {len(recon)} endpoint partitions, {len(cases)} case interval rows, {len(preservation)} protected files',flush=True)


if __name__=='__main__':
    run()
