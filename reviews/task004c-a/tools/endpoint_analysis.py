"""Offline only: existing GT and fixed-scale native-keyframe endpoint measures."""
import os,sys,pathlib,json,csv,hashlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(A/'release/tools'))
import endpoints as ep
from contracts import S_REF,GT_SHA
GT=ROOT.parents[1]/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write_csv(name,rows):
 with (ROOT/'results'/name).open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def safeangle(r):return float(np.degrees(np.arccos(np.clip((np.trace(r)-1)/2,-1,1))))
def metric(mats,gt,R):
 p,q=mats[312],mats[328];g,h=gt[311],gt[327]
 t=p[:3,:3].T@(q[:3,3]-p[:3,3]);tg=g[:3,:3].T@(h[:3,3]-g[:3,3]);ln=np.linalg.norm(t);gn=np.linalg.norm(tg)
 return dict(raw_endpoint_length=float(ln),gt_endpoint_length_game_units=float(gn),fixed_scale=S_REF,fixed_scale_displacement_ratio_pct=float(100*S_REF*ln/gn),absolute_ratio_gap_pct=float(abs(100*S_REF*ln/gn-100)),translation_rpe_fixed_scale_game_units=float(np.linalg.norm(S_REF*t-tg)),relative_camera_direction_error_deg=float(np.degrees(np.arccos(np.clip(t@tg/(ln*gn),-1,1)))) if ln>1e-10 and gn>1e-10 else None,rotation_rpe_deg=safeangle((g[:3,:3].T@h[:3,:3]).T@(p[:3,:3].T@q[:3,:3])),world_direction_error_frozen_prefix_alignment_deg=float(np.degrees(np.arccos(np.clip((R@(q[:3,3]-p[:3,3]))@(h[:3,3]-g[:3,3])/(ln*gn),-1,1)))) if R is not None and ln>1e-10 else None)
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and sha(GT)==GT_SHA
 gt=ep.read_gt(GT);rows=[];effects=[];pose_rows=[]
 for arm in ['E0','E1']:
  folder=ROOT/'native_small'/arm;m=json.loads((folder/'CHECKPOINT.json').read_text());ids=np.load(folder/'timestamp.npy',allow_pickle=False)[:m['active_count']].astype(int)+1;p0=np.load(folder/'poses.npy',allow_pickle=False);base={int(rgb):ep.pose_matrix(p,'W2C') for rgb,p in zip(ids,p0)};R,fit=ep.alignment_rotation(base,gt);before=metric(base,gt,R);rows.append(dict(arm=arm,D='BEFORE',source='NATIVE_KEYFRAME_BA_INPUT',state_id=m['state_id'],**before));vals={}
  for D in [1,0]:
   d=ROOT/'native_small'/f'{arm}_D{D}';p1=np.load(d/'poses_native.npy',allow_pickle=False);mats={int(rgb):ep.pose_matrix(p,'W2C') for rgb,p in zip(ids,p1)};v=metric(mats,gt,R);vals[D]=v
   rows.append(dict(arm=arm,D=D,source='NATIVE_AFTER_TWO_INNER_ITERATIONS_NO_FILLER',state_id=m['state_id'],**v))
   for slot,rgb in enumerate(ids):
    a,b=base[int(rgb)],mats[int(rgb)];pose_rows.append(dict(arm=arm,D=D,slot=slot,rgb_id=int(rgb),inside_pose_window=m['scalars']['t0']<=slot<m['scalars']['t1'],camera_center_update_raw=float(np.linalg.norm(b[:3,3]-a[:3,3])),w2c_translation_component_delta_l2=float(np.linalg.norm(p1[slot,:3]-p0[slot,:3])),rotation_update_deg=safeangle(a[:3,:3].T@b[:3,:3])))
  effect={k:vals[1][k]-vals[0][k] for k in vals[1] if isinstance(vals[1][k],(int,float)) and vals[0][k] is not None and k not in ['gt_endpoint_length_game_units','fixed_scale']}
  effects.append(dict(arm=arm,state_id=m['state_id'],contrast='D1_MINUS_D0',branch_clones=2,independent_source_states=1,same_D_repeat_count=1,**effect))
 write_csv('TASK004C_FIXED_STATE_ENDPOINT_METRICS.csv',rows);write_csv('TASK004C_FIXED_STATE_D_EFFECTS.csv',effects);write_csv('TASK004C_PER_POSE_UPDATES.csv',pose_rows)
 (ROOT/'results/GT_EVALUATION_IDENTITY.json').write_text(json.dumps(dict(gt_path=str(GT),sha256=GT_SHA,fixed_scale=S_REF,GT_used_only_offline=True,camera_frame_mapping='rgb_id_minus_1',pose_convention='native W2C converted via historical audited helper',alignment_note='One prefix-before rotation per state, held fixed across branches; no branch refitting',unit='game units; no meter assertion',torch_imported='torch' in sys.modules),indent=2))
 print(json.dumps({'endpoints':rows,'D1_minus_D0':effects},indent=2))
if __name__=='__main__':main()
