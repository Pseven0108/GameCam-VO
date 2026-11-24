"""Traceable per-frame, case, and consecutive-keyframe records."""
from metrics import CASE, CASE_INTERVALS, CLASSES, MODELS, PAIR_TYPES, THIRDS, angles, endpoint_type, pose_errors, relative, np
from audit_common import OFFSETS, require


def frame_rows(meta, model, d, peer, ids, phase):
    for k,rgb in enumerate(ids):
        status=str(d['status'][k]); valid=status=='VALID'
        src=CLASSES[0 if d['source'][k] else 1]
        origin=('FINAL_BA_ANCHOR_REINSERTED' if model==MODELS[1] and src=='KEYFRAME' else 'FILLER_OUTPUT')
        yield dict(**meta,model=model,rgb_id=int(rgb),camera_id=int(rgb)-1,local_index=k,
                   trajectory_sha256=d['trajectory_sha256'],expected_source_type=src,frame_type=src if valid else status,
                   pose_status=status,pose_origin=origin,other_model_source_type=CLASSES[0 if peer['source'][k] else 1],
                   other_model_pose_status=peer['status'][k],temporal_third=THIRDS[phase[k]],align_scale=d['scale'],
                   trajectory_row_0based=int(d['slot'][k]) if d['slot'][k]>=0 else None,
                   translation_error_game_units=float(d['translation'][k]) if valid else None,
                   rotation_error_deg=float(d['angle'][k]) if valid else None)


def adjacent_and_direct(ev,meta,model,d,ids,truth,phase):
    loc=np.flatnonzero(d['source']); i,j=loc[:-1],loc[1:]
    pr=np.r_[0,np.cumsum(~d['valid'])]; ok=pr[j+1]==pr[i]
    v=np.full((len(i),4),np.nan); v[ok]=relative(ev,d,truth,i[ok],j[ok]); adj=[]; direct_rows=[]
    info=dict(**meta,model=model,trajectory_sha256=d['trajectory_sha256'])
    dv=None
    if d['direct'] is not None:
        from scipy.spatial.transform import Rotation
        direct=d['direct']; dr=Rotation.from_quat(direct[:,3:]).as_matrix()
        p,te,re=pose_errors(direct,dr,truth[loc],d['r'],d['t'],d['scale'])
        for x,k in enumerate(loc):
            direct_rows.append(dict(**info,rgb_id=int(ids[k]),camera_id=int(ids[k]-1),temporal_third=THIRDS[phase[k]],
                direct_translation_error_game_units=float(te[x]),direct_rotation_error_deg=float(re[x]),
                exported_translation_error_game_units=float(d['translation'][k]),exported_rotation_error_deg=float(d['angle'][k]),
                export_vs_direct_position_delta=float(np.linalg.norm(p[x]-d['point'][k])),
                export_vs_direct_rotation_delta_deg=float(angles((dr[x].T@d['rot'][k])[None])[0])))
        k=np.arange(len(loc)-1); dv=relative(ev,dict(pred=direct,rot=dr,scale=d['scale']),truth[loc],k,k+1)
    for row,(a,b,g,(e2,ro,u,r)) in enumerate(zip(i,j,ok,v)):
        adj.append(dict(**info,first_rgb=int(ids[a]),last_rgb=int(ids[b]),actual_rgb_gap=int(ids[b]-ids[a]),
            valid_complete_interval=bool(g),translation_rpe_game_units=float(np.sqrt(e2)) if g else None,
            rotation_rpe_deg=float(ro) if g else None,gt_step_game_units=float(u) if g else None,
            scaled_displacement_ratio=float(r) if np.isfinite(r) else None,
            direct_slam_translation_rpe_game_units=float(np.sqrt(dv[row,0])) if dv is not None else None,
            direct_slam_rotation_rpe_deg=float(dv[row,1]) if dv is not None else None,
            pose_source='FINAL_BA_ANCHORS_REINSERTED' if model==MODELS[1] else 'FILLER_OUTPUT_AT_FINAL_KEYFRAME_IDS'))
    return adj,direct_rows


def case_pair(ev,meta,ids,truth,name,d,a,b):
    i,j=np.searchsorted(ids,[a,b]); ii,jj=ev.pairs(ids,b-a,d['valid'])
    require(ids[i]==a and ids[j]==b and np.any((ii==i)&(jj==j)),f'invalid case interval {a}->{b}')
    e2,ro,gt,ratio=relative(ev,d,truth,np.array([i]),np.array([j]))[0]
    shift=d['point'][j]-d['point'][i]; ref=truth[j,:3,3]-truth[i,:3,3]
    k=d['keys']; left=k[k<=a]; right=k[k>=b]
    return dict(**meta,model=name,trajectory_sha256=d['trajectory_sha256'],first_rgb=int(a),last_rgb=int(b),
        first_camera_id=int(a)-1,last_camera_id=int(b)-1,offset=int(b-a),formal_offset=b-a in OFFSETS,
        endpoint_type=PAIR_TYPES[endpoint_type(d['source'],i,j)],
        first_position_error_game_units=float(d['translation'][i]),last_position_error_game_units=float(d['translation'][j]),
        first_rotation_error_deg=float(d['angle'][i]),last_rotation_error_deg=float(d['angle'][j]),
        translation_rpe_game_units=float(np.sqrt(e2)),rotation_rpe_deg=float(ro),gt_step_game_units=float(gt),
        scaled_displacement_ratio=float(ratio) if np.isfinite(ratio) else None,
        aligned_world_displacement_error_game_units=float(np.linalg.norm(shift-ref)),
        previous_or_equal_keyframe_rgb=int(left[-1]) if len(left) else None,
        next_or_equal_keyframe_rgb=int(right[0]) if len(right) else None)


def case_records(ev,meta,ids,truth,model,d,models):
    true=truth[:,:3,3]
    series=[dict(**meta,model=model,rgb_id=int(t),keyframe=bool(d['source'][k]),
                 translation_error_game_units=float(d['translation'][k]),rotation_error_deg=float(d['angle'][k]),
                 **{f'gt_{m}':float(true[k,c]) for c,m in enumerate('xyz')},
                 **{f'aligned_{m}':float(d['point'][k,c]) for c,m in enumerate('xyz')}) for k,t in enumerate(ids)]
    rows=[]; requests=set(); keys=d['keys']
    for a,b in CASE_INTERVALS:
        rows.append(case_pair(ev,meta,ids,truth,model,d,a,b))
        for rgb in (a,b):
            lo=keys[keys<=rgb]; hi=keys[keys>rgb]
            if len(lo) and len(hi): requests.add((int(lo[-1]),int(hi[0]),f'near_{rgb}'))
        lo=keys[keys<=a]; hi=keys[keys>=b]
        if len(lo) and len(hi): requests.add((int(lo[-1]),int(hi[0]),f'bracket_{a}_{b}'))
    anchors=[dict(**case_pair(ev,meta,ids,truth,name,other,a,b),anchors_selected_from=model,role=role)
             for a,b,role in sorted(requests) for name,other in models.items()]
    return rows,series,anchors
