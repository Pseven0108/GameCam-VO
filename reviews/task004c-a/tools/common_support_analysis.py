"""CPU-only same-observation-support diagnostics, not native inner instrumentation."""
import os,sys,json,pathlib,csv,time
import numpy as np
from geometry_analysis import qmul,qrot,load_state,stats
from checkpoint_io import new_json

def projected(m,a,p,d):
 fx,fy,cx,cy=np.asarray(a['K'],dtype=float);h,w=a['disps'].shape[1:];y,x=np.mgrid[:h,:w];rays=np.stack(((x-cx)/fx,(y-cy)/fy,np.ones_like(x)),axis=-1);res=[];valid=[]
 for e,(i,j) in enumerate(zip(a['ii'],a['jj'])):
  i,j=int(i),int(j);qi=np.asarray(p[i,3:],dtype=float);qj=np.asarray(p[j,3:],dtype=float);q=qmul(qj,qi*np.array([-1,-1,-1,1]));t=p[j,:3]-qrot(q,p[i,:3])
  if i==j:q=np.array([0.,0.,0.,1.]);t=np.array([-.1,0.,0.])
  v=qrot(q,rays)+np.asarray(d[i])[...,None]*t;ok=np.isfinite(v).all(-1)&(v[...,2]>=.25);iz=np.divide(1.,v[...,2],out=np.zeros_like(v[...,2]),where=ok);uv=v[...,:2]*iz[...,None]*[fx,fy]+[cx,cy];r=np.moveaxis(a['target'][e],0,-1)-uv
  res.append(r);valid.append(ok&np.isfinite(r).all(-1))
 return np.stack(res),np.stack(valid)

def main(root):
 output=root/'analysis';rows=[]
 for arm in ['E0','E1']:
  m,a=load_state(root/'captures'/arm/'checkpoint');evals={};us={};p0=np.asarray(a['poses']);d0=np.asarray(a['disps']);n=m['active_count'];evals['BEFORE']=projected(m,a,p0,d0);us['BEFORE']=np.asarray(a['U'])
  for D in [1,0]:
   q=root/'replays'/f'{arm}_D{D}';evals[str(D)]=projected(m,a,np.load(q/'poses_native.npy'),np.load(q/'disps_native.npy'));us[str(D)]=np.load(q/'U_native.npy')
  mask=np.logical_and.reduce([v[1] for v in evals.values()]);basew=np.moveaxis(a['weight'],1,-1).astype(float)*.001;ii=np.asarray(a['ii']);sourceU=np.asarray(a['U'])[ii];f=np.clip(1/np.maximum(45*sourceU-35,.1),0,1);weights=basew*f[...,None]
  for D,(r,ok) in evals.items():
   fu=np.clip(1/np.maximum(45*us[D][ii]-35,.1),0,1)
   rows.append(dict(state=arm,D=D,total_edge_pixels=int(mask.size),common_valid_pixels=int(mask.sum()),individual_valid_pixels=int(ok.sum()),common_support_sse_frozen_initial_U=float(np.sum(weights[mask]*r[mask]**2)),common_support_rms_lowres_px=float(np.sqrt(np.mean(np.sum(r[mask]**2,axis=-1)))),common_support_sse_current_U=float(np.sum((basew*fu[...,None])[mask]*r[mask]**2)),effective_uba_mean_initial=float(np.mean(f)),effective_uba_mean_current=float(np.mean(fu)),U_active_median=float(np.median(us[D][:n])),U_active_p90=float(np.quantile(us[D][:n],.9)),U_active_p95=float(np.quantile(us[D][:n],.95))))
  kx=np.unique(np.r_[np.arange(m['scalars']['t0'],m['scalars']['t1']),a['ii']]);mono=np.asarray(a['mono_disps'][kx],dtype=float);delta=np.asarray(a['disps'][kx],dtype=float)-mono;terms=np.load(output/(arm+'_INITIAL_DEPTH_NORMAL_TERMS.npz'),allow_pickle=False);C=terms['C_geometry'];b=terms['b_geometry'];msk=mono>0;bp=-(msk*m['scalars']['gamma_depth']*delta)
  report=dict(state=arm,depth_pixels=len(delta.ravel()),valid_prior_pixels=int(msk.sum()),initial_disparity=stats(np.asarray(a['disps'][kx],dtype=float)),mono_disparity=stats(mono),initial_mono_difference=stats(delta),initial_C_geometry=stats(C),prior_C=m['scalars']['gamma_depth'],fraction_prior_C_gt_geometry_on_prior_support=float(np.mean(m['scalars']['gamma_depth']>C[msk])),b_geometry_l2=float(np.linalg.norm(b)),b_prior_l2=float(np.linalg.norm(bp)),fraction_abs_bprior_gt_bgeometry=float(np.mean(np.abs(bp[msk])>np.abs(b[msk]))),eta=stats(np.asarray(a['eta'])),full_schur_condition_number=None,full_schur_not_captured=True,classification='CPU_RECONSTRUCTION_INITIAL_LINEARIZATION_ONLY')
  new_json(output/(arm+'_PRIOR_VS_GEOMETRY.json'),report)
 with (output/'COMMON_SUPPORT_RESIDUALS.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(json.dumps(rows,indent=2))
if __name__=='__main__':
 t=time.monotonic();out=pathlib.Path(sys.argv[1])/'analysis';ec=0
 try:
  assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
  main(pathlib.Path(sys.argv[1]))
 except Exception:
  ec=1;__import__('traceback').print_exc()
 finally:new_json(out/'COMMON_SUPPORT_PROCESS.json',dict(exit_code=ec,elapsed_seconds=time.monotonic()-t,torch_imported='torch' in sys.modules))
 sys.exit(ec)
