"""Aggregate only within calibration branch; compare across original sequences."""
import csv
from collections import Counter,defaultdict
from itertools import groupby

from decompose import write_csv,write_json,require
from metrics import OUT,PAIR_TYPES,MODELS,CASE,np,fmt
from audit_common import FIXED,VIRTUAL,OFFSETS,read_csv

METRICS=('translation','rotation')
DRAWS=10000
SEED=20261122


def seq_pool(rows, keys):
    pool={}
    for r in rows:
        k=tuple(r[f] for f in keys); v=pool.setdefault(k,[0,0,0.,0.,0])
        v[0]+=int(r['expected_count']);v[1]+=int(r['valid_count'])
        v[2]+=float(r['translation_sse']);v[3]+=float(r['rotation_sse']);v[4]+=1
    return [dict(zip(keys,k),expected_pairs_or_frames=v[0],valid_pairs_or_frames=v[1],
                invalid_or_missing_count=v[0]-v[1],coverage=v[1]/v[0] if v[0] else None,
                translation_sse=v[2],rotation_sse=v[3],segments=v[4],
                translation_rmse=float(np.sqrt(v[2]/v[1])) if v[1] else None,
                rotation_rmse=float(np.sqrt(v[3]/v[1])) if v[1] else None) for k,v in sorted(pool.items())]


def sequence_compare(seqrows, keys, strata, cases, idcol, labels):
    tables=defaultdict(dict)
    for r in seqrows:
        if r[idcol] not in cases: continue
        for env in (r['environment'],'ALL_ENVIRONMENTS'):
            k=(r['calibration_branch'],env,*(r[f] for f in keys))
            slot=tables[k].setdefault(r['sequence'],{})
            require(r[idcol] not in slot,'duplicate per-sequence score')
            slot[r[idcol]]=r
    results=[]
    for (branch,env,*g),seqs in sorted(tables.items()):
        pool=[v for k,v in sorted(seqs.items()) if all(x in v and v[x]['valid_pairs_or_frames'] for x in cases)]
        counts=[sum(v[x]['valid_pairs_or_frames'] for v in pool) for x in cases]
        n=len(pool)
        paired_ids=';'.join(k for k,v in sorted(seqs.items()) if all(x in v and v[x]['valid_pairs_or_frames'] for x in cases))
        # One shared bootstrap vector per contrast, used on both methods and both metrics.
        idx=np.random.default_rng(SEED).integers(0,n,size=(DRAWS,n)) if n>=5 else None
        for metric in METRICS:
            xy=np.array([[q[x][metric+'_rmse'] for x in cases] for q in pool]).reshape(-1,2)
            delta=xy[:,1]-xy[:,0]
            row=dict(calibration_branch=branch,environment=env,**dict(zip(keys,g)),contrast=strata,metric=metric,
                     left_label=labels[0],right_label=labels[1],sequences_in_scope=len(seqs),paired_sequences=n,
                     excluded_sequences=len(seqs)-n,paired_sequence_ids=paired_ids,left_valid_count=counts[0],right_valid_count=counts[1],
                     support='EMPTY' if n==0 else ('UNSTABLE_N_LT5' if n<5 else 'DESCRIPTIVE_BOOTSTRAP'),
                     left_seq_rmse_mean=None,right_seq_rmse_mean=None,left_seq_rmse_p10=None,right_seq_rmse_p10=None,
                     left_seq_rmse_median=None,right_seq_rmse_median=None,left_seq_rmse_p90=None,right_seq_rmse_p90=None,
                     mean_delta_right_minus_left=None,median_delta=None,mean_delta_ci95_low=None,mean_delta_ci95_high=None,
                     left_available_sequences=sum(cases[0] in v and bool(v[cases[0]]['valid_pairs_or_frames']) for v in seqs.values()),
                     right_available_sequences=sum(cases[1] in v and bool(v[cases[1]]['valid_pairs_or_frames']) for v in seqs.values()),
                     right_higher_sequences=None,right_lower_sequences=None,exact_ties=None)
            if n:
                q10,q50,q90=np.quantile(xy,[.1,.5,.9],axis=0)
                row.update(left_seq_rmse_mean=float(xy[:,0].mean()),right_seq_rmse_mean=float(xy[:,1].mean()),
                    left_seq_rmse_p10=float(q10[0]),right_seq_rmse_p10=float(q10[1]),
                    left_seq_rmse_median=float(q50[0]),right_seq_rmse_median=float(q50[1]),
                    left_seq_rmse_p90=float(q90[0]),right_seq_rmse_p90=float(q90[1]),
                    mean_delta_right_minus_left=float(delta.mean()),median_delta=float(np.median(delta)),
                    right_higher_sequences=int((delta>0).sum()),right_lower_sequences=int((delta<0).sum()),exact_ties=int((delta==0).sum()))
                if idx is not None:
                    lo,hi=np.quantile(delta[idx].mean(axis=1),[.025,.975])
                    row.update(mean_delta_ci95_low=float(lo),mean_delta_ci95_high=float(hi))
            results.append(row)
    return results


def frame_pair_stats():
    frames=read_csv(OUT/'POSE_ERROR_BY_SEGMENT_AND_TIME.csv')
    pairs=read_csv(OUT/'RPE_BY_ENDPOINT_TYPE.csv')
    framekeys=('calibration_branch','environment','sequence','population','frame_type','temporal_third','model')
    pairkeys=('calibration_branch','environment','sequence','population','endpoint_type','slam_type','wild_type','offset','model')
    fs=seq_pool(frames,framekeys); rs=seq_pool(pairs,pairkeys)
    write_csv('POSE_ERROR_BY_SEQUENCE.csv',fs);write_csv('RPE_ENDPOINT_TYPE_BY_SEQUENCE.csv',rs)
    f_env=sequence_compare(fs,('population','frame_type','temporal_third'),'W_MINUS_SLAM',MODELS,'model',MODELS)
    f_within=[]
    for model in MODELS:
        rr=[dict(**r,within_model=model) for r in fs if r['population']=='OWN' and r['model']==model]
        f_within+=sequence_compare(rr,('within_model','temporal_third'),'FILLED_MINUS_KEYFRAME',
            ('KEYFRAME','FILLED_FRAME'),'frame_type',('KEYFRAME','FILLED_FRAME'))
    p_own=sequence_compare([r for r in rs if r['population']=='OWN'],('endpoint_type','offset'),
                           'W_MINUS_SLAM_OWN_CLASS_MAY_DIFFER_IN_RGB',MODELS,'model',MODELS)
    # In OWN rows use the explicit endpoint_type to avoid pooling four strata into one cell.
    p_env=sequence_compare([r for r in rs if r['population']=='MATCHED_CLASS_GRID'],('population','slam_type','wild_type','offset'),
                           'W_MINUS_SLAM_MATCHED_RGB',MODELS,'model',MODELS)
    p_within=[]
    for model in MODELS:
        rr=[dict(**r,within_model=model) for r in rs if r['population']=='OWN' and r['model']==model]
        p_within+=sequence_compare(rr,('within_model','offset'),'FF_MINUS_KK_OWN',
            (PAIR_TYPES[0],PAIR_TYPES[3]),'endpoint_type',(PAIR_TYPES[0],PAIR_TYPES[3]))
    for n,x in [('POSE_ERROR_ENVIRONMENT_PAIRED.csv',f_env),('POSE_FILL_VS_KEYFRAME_BY_TIME.csv',f_within),
                ('RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv',p_own+p_env),('RPE_OWN_FILL_VS_KEYFRAME.csv',p_within)]:
        write_csv(n,x)
    return fs,rs,f_env,f_within,p_own,p_env,p_within


def stratification_and_screen(index):
    strata=defaultdict(lambda:[0,0.,0.]); screens=defaultdict(lambda:[0,0,0]); hit=[]
    with (OUT/'RPE_PAIR_DETAIL.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            sid=int(r['segment_index']);off=int(r['offset']);sc=int(r['slam_type']);wc=int(r['wild_type']);rgb=int(r['start_rgb'])
            meta=index[sid]
            if r['slam_interval_status']!='VALID' or r['wild_interval_status']!='VALID': continue
            for m,c,stem in ((MODELS[0],sc,'slam'),(MODELS[1],wc,'wild')):
                if c in (0,3):
                    v=strata[sid,m,off,r['temporal_third'],int(r['gt_motion_bin']),c]
                    v[0]+=1;v[1]+=float(r[stem+'_trans_error_sq']);v[2]+=float(r[stem+'_rot_deg'])**2
            if int(r['gt_screen_pass']) and r['wild_scaled_ratio'] and r['slam_scaled_ratio']:
                s=float(r['slam_scaled_ratio']); w=float(r['wild_scaled_ratio']); k=(sid,off,sc,wc)
                v=screens[k];v[0]+=1;v[1]+=int(w<.5)
                if w<.5 and .8<=s<=1.2:
                    v[2]+=1; hit.append((sid,off,sc,wc,rgb,s,w))
    standardized=[]; detail=[]
    for minimum in (1,5):
        accum=defaultdict(lambda:[0,0.,0.,0.,0.,0])
        for k,a in sorted(strata.items()):
            sid,m,off,phase,gtbin,c=k
            if c!=0: continue
            b=strata.get((*k[:-1],3),[0,0.,0.]); w=min(a[0],b[0]); meta=index[sid]
            if w<minimum: continue
            v=accum[meta['calibration_branch'],meta['environment'],meta['sequence'],m,off]
            vals=[a[1]/a[0],a[2]/a[0],b[1]/b[0],b[2]/b[0]]
            for i,val in enumerate(vals,1): v[i]+=w*val
            v[0]+=w;v[5]+=1
            if minimum==1:
                detail.append(dict(**meta,model=m,offset=off,temporal_third=phase,gt_step_tertile=gtbin,
                                   kk_pairs=a[0],ff_pairs=b[0],common_weight=w,kk_trans_mse=vals[0],ff_trans_mse=vals[2],
                                   kk_rotation_mse=vals[1],ff_rotation_mse=vals[3]))
        allseq={(m['calibration_branch'],m['environment'],m['sequence']) for m in index.values()}
        for branch,env,seq in sorted(allseq):
            for m in MODELS:
                for off in OFFSETS:
                    w,kt,kr,ft,fr,bins=accum[branch,env,seq,m,off]
                    for cls,tr,ro in ((PAIR_TYPES[0],kt,kr),(PAIR_TYPES[3],ft,fr)):
                        standardized.append(dict(calibration_branch=branch,environment=env,sequence=seq,model=m,offset=off,
                            min_pairs_each_class_per_stratum=minimum,endpoint_type=cls,overlap_strata=bins,valid_pairs_or_frames=w,
                            translation_rmse=float(np.sqrt(tr/w)) if w else None,rotation_rmse=float(np.sqrt(ro/w)) if w else None))
    envstats=sequence_compare(standardized,('model','offset','min_pairs_each_class_per_stratum'),
                              'FF_MINUS_KK_STANDARDIZED_WITHIN_SEGMENT_TIME_GT_MOTION',
                              (PAIR_TYPES[0],PAIR_TYPES[3]),'endpoint_type',(PAIR_TYPES[0],PAIR_TYPES[3]))
    write_csv('RPE_TIME_MOTION_STRATA.csv',detail);write_csv('RPE_STANDARDIZED_BY_SEQUENCE.csv',standardized)
    write_csv('RPE_STANDARDIZED_FILL_VS_KEYFRAME.csv',envstats)
    screenrows=[dict(**index[sid],offset=off,slam_type=PAIR_TYPES[sc],wild_type=PAIR_TYPES[wc],
                     screened_pairs=v[0],wild_lt_half_pairs=v[1],wild_lt_half_with_slam_control_pairs=v[2])
                for (sid,off,sc,wc),v in sorted(screens.items())]
    hitrows=[]; runs=[]
    for k,xs in groupby(sorted(hit),key=lambda x:x[:4]):
        sid,off,sc,wc=k
        meta=dict(**index[sid],offset=off,slam_type=PAIR_TYPES[sc],wild_type=PAIR_TYPES[wc])
        xx=list(xs)
        hitrows.extend(dict(**meta,start_rgb=x[4],end_rgb=x[4]+off,slam_scaled_ratio=x[5],wild_scaled_ratio=x[6]) for x in xx)
        for _,series in groupby(enumerate(xx),lambda q:q[1][4]-q[0]):
            rows=[q[1] for q in series]
            if len(rows)>=5: runs.append(dict(**meta,start_of_starts=rows[0][4],end_of_starts=rows[-1][4],pairs=len(rows)))
    write_csv('COMPRESSION_SCREEN_BY_CLASS.csv',screenrows)
    write_csv('COMPRESSION_SCREEN_PAIRS.csv',hitrows)
    if runs: write_csv('COMPRESSION_RUNS_SAME_ENDPOINT_CLASS.csv',runs)
    return screenrows,hitrows,runs


def make_review_counts(ids, index, screens, hits, runs):
    out=[]; exposure=[]
    for branch in (FIXED,VIRTUAL):
        envs=sorted({r['environment'] for r in index.values() if r['calibration_branch']==branch})
        for env in ('ALL_ENVIRONMENTS',*envs):
            def select(r):
                return r['calibration_branch']==branch and (env=='ALL_ENVIRONMENTS' or r['environment']==env)
            ks=[r for r in ids if r['model']==MODELS[0] and select(r)]
            cnt={k:sum(int(x[k]) for x in ks) for k in ('input_frames','shared_kf','both_filled','slam_kf_only','wild_kf_only')}
            n=cnt['input_frames']; diff=cnt['slam_kf_only']+cnt['wild_kf_only']
            require(cnt['shared_kf']+cnt['both_filled']+diff==n,'frame membership does not partition')
            seqs={r['sequence'] for r in ks}
            row=dict(calibration_branch=branch,environment=env,sequences=len(seqs),segments=len(ks),**cnt,
                     differing_keyframe_membership=diff,differing_fraction=diff/n,
                     slam_kf=cnt['shared_kf']+cnt['slam_kf_only'],wild_kf=cnt['shared_kf']+cnt['wild_kf_only'],
                     same_keyframe_id_set_segments=sum(r['same_kf_set']=='True' for r in ks))
            exposure.append(row)
            for off in OFFSETS:
                ss=[r for r in screens if select(r) and r['offset']==off]
                hs=[r for r in hits if select(r) and r['offset']==off]
                rr=[r for r in runs if select(r) and r['offset']==off]
                for t in ('ALL',*PAIR_TYPES):
                    for agree in ('ANY_SLAM_TYPE','SAME_TYPE_ONLY'):
                        if t=='ALL' and agree=='SAME_TYPE_ONLY': continue
                        def typ(r):
                            return (t=='ALL' or r['wild_type']==t) and (agree=='ANY_SLAM_TYPE' or r['slam_type']==t)
                        good=[r for r in hs if typ(r)]; seq_hit=len({r['sequence'] for r in good})
                        run=[r for r in rr if typ(r)]
                        screened=sum(r['screened_pairs'] for r in ss if typ(r))
                        out.append(dict(calibration_branch=branch,environment=env,offset=off,wild_type=t,comparison=agree,
                            sequences=len(seqs),sequences_with_screened_pairs=len({r['sequence'] for r in ss if typ(r)}),
                            screened_pairs=screened,hit_pairs=len(good),hit_fraction=len(good)/screened if screened else None,
                            sequences_with_hits=seq_hit,runs_at_least_five_same_cross_class=len(run),
                            sequences_with_runs=len({r['sequence'] for r in run})))
    write_csv('KEYFRAME_MEMBERSHIP_BY_ENVIRONMENT.csv',exposure)
    write_csv('COMPRESSION_RECURRENCE_BY_ENVIRONMENT.csv',out)
    return exposure,out


def case_comparators():
    cases=read_csv(OUT/'VAL007_CASE_INTERVALS.csv')
    pairs=read_csv(OUT/'VAL007_SAME_OFFSET_PAIRS.csv'); result=[]
    for case in cases:
        m=case['model']; off=case['offset']; p='wild' if m==MODELS[1] else 'slam'
        q='slam' if p=='wild' else 'wild'; target=case['endpoint_type']
        ref=next(x for x in pairs if x['offset']==off and x['first_rgb']==case['first_rgb'])
        for both in (False,True):
            a=[x for x in pairs if x['offset']==off and x['first_rgb']!=case['first_rgb'] and x['gt_screen_pass']=='True'
               and x[p+'_type']==target and (not both or x[q+'_type']==ref[q+'_type'])]
            x=np.array([float(r[p+'_ratio']) for r in a if r[p+'_ratio']]); tr=np.array([float(r[p+'_trans_error']) for r in a]);
            result.append(dict(model=m,first_rgb=int(case['first_rgb']),last_rgb=int(case['last_rgb']),offset=int(off),
                endpoint_type=target,comparison='EXACT_CROSS_CLASS' if both else 'OWN_TYPE_ONLY',
                slam_type=ref['slam_type'],wild_type=ref['wild_type'],other_pairs=len(a),ratio_count=len(x),
                ratio_median=float(np.median(x)) if len(x) else None,ratio_p10=float(np.quantile(x,.1)) if len(x) else None,
                ratio_case_empirical_fraction_at_or_below=float(np.mean(x<=float(case['scaled_displacement_ratio']))) if len(x) else None,
                translation_error_median=float(np.median(tr)) if len(tr) else None,
                case_pair_passes_gt_motion_screen=ref['gt_screen_pass']=='True'))
    write_csv('VAL007_SAME_TYPE_COMPARATORS.csv',result)
    return result


def main():
    fs,rs,fe,fw,po,pe,pw=frame_pair_stats()
    index={int(r['segment_index']):r for r in read_csv(OUT/'RPE_PAIR_SEGMENT_INDEX.csv')}
    ss,hs,rr=stratification_and_screen(index)
    exposure,rec=make_review_counts(read_csv(OUT/'KEYFRAME_ID_AUDIT.csv'),index,ss,hs,rr)
    comp=case_comparators()
    def divs(x):
        return dict(median=float(np.median(x)),p95=float(np.quantile(x,.95)),max=float(np.max(x)))
    direct=read_csv(OUT/'DIRECT_FINAL_BA_ANCHOR_COMPARISON.csv')
    adj=read_csv(OUT/'KEYFRAME_CONSECUTIVE_RPE.csv')
    source_summary=[]
    for branch in (FIXED,VIRTUAL):
        for name in MODELS:
            a=[r for r in adj if r['model']==name and r['calibration_branch']==branch]
            d=[r for r in direct if r['calibration_branch']==branch]
            gaps=np.array([float(r['actual_rgb_gap']) for r in a]); errors=np.array([float(r['translation_rpe_game_units']) for r in a]);
            source_summary.append(dict(calibration_branch=branch,model=name,adjacent_pairs=len(a),gap_rgb=divs(gaps),
                translation_rpe_descriptive_variable_gap=divs(errors),
                direct_anchors=len(d) if name==MODELS[0] else None,
                exported_vs_direct_position_delta=divs([float(r['export_vs_direct_position_delta']) for r in d]) if name==MODELS[0] else None,
                exported_vs_direct_angle_deg=divs([float(r['export_vs_direct_rotation_delta_deg']) for r in d]) if name==MODELS[0] else None))
    write_json('evidence/AGGREGATE_SUMMARY.json',dict(sequence_frame_rows=len(fs),sequence_pair_rows=len(rs),
        frame_contrast_rows=len(fe)+len(fw),pair_contrast_rows=len(po)+len(pe)+len(pw),
        compression_screen_pair_hits=len(hs),same_class_consecutive_runs=len(rr),adjacent_and_direct=source_summary,
        case_comparators=comp,bootstrap_draws=DRAWS,bootstrap_seed=SEED,sequence_unit='original VIPER sequence; no cross-segment pairing'))
    print(f'PASS: {len(fs)} sequence pose strata; {len(rs)} sequence pair strata; {len(hs)} screened hit-pairs; {len(rr)} same-class runs')


if __name__=='__main__':
    main()
