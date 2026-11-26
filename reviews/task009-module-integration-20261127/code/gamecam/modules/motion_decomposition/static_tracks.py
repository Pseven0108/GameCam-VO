"""Original conservative adapter; 2D tracks are not labeled 3D motion."""
import numpy as np


def track_to_correspondences(total_xy, static_xyz, visibility, dynamic_probability,
                             source_index, target_index, image_hw,
                             min_visibility=0.9, max_dynamic=0.1):
    xy=np.asarray(total_xy);st=np.asarray(static_xyz);v=np.asarray(visibility);d=np.asarray(dynamic_probability)
    if xy.ndim!=3 or xy.shape[-1]!=2 or st.shape!=(*xy.shape[:2],3) or v.shape!=xy.shape[:2] or d.shape!=v.shape:
        raise ValueError("Expected [T,P,2], [T,P,3], and [T,P] tracker arrays")
    a,b=int(source_index),int(target_index)
    good=(v[a]>=min_visibility)&(v[b]>=min_visibility)&(d[a]<=max_dynamic)&(d[b]<=max_dynamic)
    good &= np.isfinite(xy[a]).all(-1)&np.isfinite(st[b]).all(-1)&(st[b,:,2]>0)
    h,w=image_hw
    for p in (xy[a],st[b,:,:2]):good&=(p[:,0]>=0)&(p[:,0]<w)&(p[:,1]>=0)&(p[:,1]<h)
    # MDTracker static path is a counterfactual static correspondence; do not
    # add it to the same dense residual as an independent duplicate observation.
    return {"source_xy":xy[a,good],"target_static_xy":st[b,good,:2],
            "target_predicted_depth":st[b,good,2],"track_ids":np.flatnonzero(good),
            "kind":"counterfactual_static_correspondence", "metric_depth_verified":False}


def backproject(xy, depth, intrinsics):
    xy=np.asarray(xy,dtype=np.float64);z=np.asarray(depth,dtype=np.float64)
    fx,fy,cx,cy=np.asarray(intrinsics,dtype=np.float64)
    if min(fx,fy)<=0 or xy.shape!=(*z.shape,2) or not np.isfinite(z).all() or (z<=0).any():
        raise ValueError("Invalid calibrated backprojection")
    return np.stack(((xy[...,0]-cx)*z/fx,(xy[...,1]-cy)*z/fy,z),-1)


def static_rigid_pose(source_xy, target_xy, source_depth, target_depth, intrinsics):
    """Diagnostic 3D-3D rigid fit, never an automatic native-BA constraint."""
    p=backproject(source_xy,source_depth,intrinsics);q=backproject(target_xy,target_depth,intrinsics)
    if len(p)<6:raise ValueError("At least six visible static points required")
    pc=p-p.mean(0);qc=q-q.mean(0)
    if np.linalg.matrix_rank(pc)<2:raise ValueError("Degenerate static geometry")
    u,s,vt=np.linalg.svd(pc.T@qc);corr=np.eye(3);corr[-1,-1]=np.linalg.det(vt.T@u.T)
    rotation=vt.T@corr@u.T;translation=q.mean(0)-rotation@p.mean(0)
    return rotation,translation,np.linalg.norm((rotation@p.T).T+translation-q,axis=1)
