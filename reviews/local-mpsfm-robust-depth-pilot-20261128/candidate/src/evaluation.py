"""Offline-only metrics, matching GameCam-VO's sealed full-sequence scorer.

One Sim3 fit per complete 64-frame trajectory; never fit scales per RPE pair.
VIPER translations are reported in game units, without a metres claim.
"""
import numpy as np
from scipy.spatial.transform import Rotation

def fit_alignment(est,gt,scale_free):
    a,b=est-est.mean(0),gt-gt.mean(0)
    variance=np.sum(a*a)/len(a)
    if variance<=1e-14 or np.sum(b*b)<=1e-12:raise ValueError('Degenerate trajectory')
    u,d,vt=np.linalg.svd(b.T@a/len(a))
    rank=int(np.sum(d>max(d[0]*1e-10,1e-14)))
    sign=np.array([1,1,np.linalg.det(u@vt)])
    rot=(u*sign)@vt
    scale=float(d@sign/variance) if scale_free else 1.
    if scale<=0 or not np.isfinite(scale):raise ValueError('Invalid alignment scale')
    return rot,gt.mean(0)-scale*rot@est.mean(0),scale,rank

def rmse(values):return float(np.sqrt(np.mean(np.sum(values*values,axis=-1))))

def rpe(ep,er,gp,gr,ids,offset):
    by_id={int(v):i for i,v in enumerate(ids)}
    pairs=[(i,by_id[int(f)+offset]) for i,f in enumerate(ids) if int(f)+offset in by_id]
    if not pairs:return dict(pairs=0,translation_rmse=None,rotation_rmse_deg=None)
    i,j=np.asarray(pairs).T
    et=(er[i].transpose(0,2,1)@(ep[j]-ep[i])[:,:,None])[:,:,0]
    gt=(gr[i].transpose(0,2,1)@(gp[j]-gp[i])[:,:,None])[:,:,0]
    eR=er[i].transpose(0,2,1)@er[j];gR=gr[i].transpose(0,2,1)@gr[j]
    angles=np.degrees(Rotation.from_matrix(gR.transpose(0,2,1)@eR).magnitude())
    return dict(pairs=len(pairs),translation_rmse=rmse(et-gt),rotation_rmse_deg=float(np.sqrt(np.mean(angles**2))))

def evaluate(pred,truth,ids):
    if pred.shape!=truth.shape or pred.shape!=(len(ids),4,4):raise ValueError('Pose identity/shape mismatch')
    if not np.isfinite(pred).all() or not np.isfinite(truth).all():raise ValueError('Nonfinite pose')
    for pose in [pred,truth]:
        if not np.allclose(pose[:,3],np.array([0,0,0,1]),atol=1e-6):raise ValueError('Invalid homogeneous pose')
        r=pose[:,:3,:3]
        if not np.allclose(r.transpose(0,2,1)@r,np.eye(3),atol=2e-4) or not np.allclose(np.linalg.det(r),1,atol=2e-4):
            raise ValueError('Invalid camera rotation')
    ep,er=pred[:,:3,3],pred[:,:3,:3];gp,gr=truth[:,:3,3],truth[:,:3,:3]
    gp_length=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum())
    ep_length=float(np.linalg.norm(np.diff(ep,axis=0),axis=1).sum())
    row=dict(gt_path_length=gp_length,raw_est_path_length=ep_length,raw_path_ratio=ep_length/gp_length)
    for mode in ['se3','sim3']:
        q,t,s,rank=fit_alignment(ep,gp,mode=='sim3')
        aligned=s*(ep@q.T)+t
        row['ate_'+mode+'_rmse']=rmse(aligned-gp)
        if mode=='sim3':
            row.update(global_sim3_scale=s,alignment_rank=rank,ate_sim3_percent_gt_path=100*row['ate_sim3_rmse']/gp_length)
            for off in [1,15]:
                row.update({f'rpe{off}_'+k:v for k,v in rpe(aligned,q@er,gp,gr,ids,off).items()})
            return_arrays=dict(aligned_positions=aligned,position_errors=np.linalg.norm(aligned-gp,axis=1),gt_positions=gp)
    return row,return_arrays
