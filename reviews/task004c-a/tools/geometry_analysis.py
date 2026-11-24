"""CPU geometry/regularization diagnostics. Not an internal Schur/gradient capture."""
import os,sys,json,pathlib,hashlib,csv
import numpy as np
from checkpoint_io import sha_file,new_json

def qmul(a,b):
 return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),a[3]*b[3]-a[:3]@b[:3]]
def qrot(q,x):
 uv=2*np.cross(q[:3],x);return x+q[3]*uv+np.cross(q[:3],uv)
def stats(a):
 a=np.asarray(a);f=a[np.isfinite(a)];return dict(n=int(a.size),finite=int(f.size),min=float(f.min()) if f.size else None,median=float(np.median(f)) if f.size else None,p95=float(np.quantile(f,.95)) if f.size else None,max=float(f.max()) if f.size else None,l2=float(np.linalg.norm(f)))
def load_state(folder):
 folder=pathlib.Path(folder);m=json.loads((folder/'CHECKPOINT.json').read_text());a={k:np.load(folder/v['file'],mmap_mode='r',allow_pickle=False) for k,v in m['arrays'].items()};return m,a

def geometry(m,a,p,d,U=None):
 k=np.asarray(a['K'],dtype=float);fx,fy,cx,cy=k;h,w=a['disps'].shape[1:];y,x=np.mgrid[:h,:w];rays=np.stack(((x-cx)/fx,(y-cy)/fy,np.ones_like(x)),axis=-1)
 U=np.asarray(a['U'] if U is None else U);C=np.zeros((m['active_count'],h,w));b=C.copy();sum_sse=0.;valid_pixels=0;err=[];edge_rows=[]
 for e,(i,j) in enumerate(zip(a['ii'],a['jj'])):
  i=int(i);j=int(j);qi=np.asarray(p[i,3:],dtype=float);qj=np.asarray(p[j,3:],dtype=float);q=qmul(qj,qi*np.array([-1,-1,-1,1]));t=p[j,:3]-qrot(q,p[i,:3]);
  if i==j:q=np.array([0.,0.,0.,1.]);t=np.array([-.1,0.,0.])
  v=qrot(q,rays)+np.asarray(d[i])[...,None]*t;z=v[...,2];valid=np.isfinite(v).all(-1)&(z>=.25);iz=np.divide(1.,z,out=np.zeros_like(z),where=valid);pred=v[...,:2]*iz[...,None]*[fx,fy]+[cx,cy];target=np.moveaxis(a['target'][e],0,-1);r=target-pred
  f=np.clip(1/np.maximum(45*U[i]-35,.1),0,1);weights=np.moveaxis(a['weight'][e],0,-1)*.001*f[...,None]*valid[...,None]
  rz=np.stack([fx*(t[0]*iz-t[2]*v[...,0]*iz**2),fy*(t[1]*iz-t[2]*v[...,1]*iz**2)],-1)
  C[i]+=np.sum(weights*rz**2,-1);b[i]+=np.sum(weights*r*rz,-1)
  vgood=valid&np.isfinite(r).all(-1);sse=float(np.sum(weights[vgood]*r[vgood]**2));sum_sse+=sse;valid_pixels+=int(vgood.sum());err.extend(np.linalg.norm(r[vgood],axis=-1).tolist())
  edge_rows.append(dict(edge=e,source_slot=i,target_slot=j,source_rgb=int(a['timestamp'][i])+1,target_rgb=int(a['timestamp'][j])+1,valid_pixels=int(vgood.sum()),weighted_sse=sse,unweighted_reprojection_rms_px=float(np.sqrt(np.mean(np.sum(r[vgood]**2,-1)))) if vgood.any() else None))
 return dict(weighted_geometry_sse=sum_sse,valid_pixels=valid_pixels,total_edge_pixels=int(len(a['ii'])*h*w),reprojection_vector_rms_lowres_px=float(np.sqrt(np.mean(np.square(err)))) if err else None,effective_uba_note='source uncertainty, full grid, geometry kernel MIN_DEPTH=.25',depth_C_stats=stats(C),depth_b_stats=stats(b)),C,b,edge_rows

def main():
 root=pathlib.Path(sys.argv[1]);output=pathlib.Path(sys.argv[2]);output.mkdir(exist_ok=True);all_summary=[]
 for arm in ('E0','E1'):
  m,a=load_state(root/'captures'/arm/'checkpoint');kx=np.unique(np.r_[np.arange(m['scalars']['t0'],m['scalars']['t1']),a['ii']]);geom0,C,b,edges=geometry(m,a,a['poses'],a['disps']);n=m['active_count'];mono=np.asarray(a['mono_disps'][kx]);d0=np.asarray(a['disps'][kx]);eta=np.asarray(a['eta']).reshape(len(kx),*d0.shape[1:]);mask=mono>0
  np.savez_compressed(output/(arm+'_INITIAL_DEPTH_NORMAL_TERMS.npz'),kx=kx,C_geometry=C[kx],b_geometry=b[kx],C_prior_D1=mask*m['scalars']['gamma_depth'],b_prior_D1=-(mask*m['scalars']['gamma_depth']*(d0-mono)),C_eta_D0=eta,b_eta_D0=np.zeros_like(eta),mono_disps=mono,disps_before=d0)
  metrics={};
  for D in (1,0):
   out=root/'replays'/f'{arm}_D{D}';rec=json.loads((out/'REPLAY_COMPLETE.json').read_text());p=np.load(out/'poses_native.npy');dn=np.load(out/'disps_native.npy');uc=np.load(out/'U_native.npy');dc=np.load(out/'disps_clamp.npy')
   gn,_,_,edges_after=geometry(m,a,p,dn);gn_u,_,_,_=geometry(m,a,p,dn,uc);gc,_,_,_=geometry(m,a,p,dc)
   gap=d0-mono;gnp=dn[kx]-mono;gcp=dc[kx]-mono;alpha=m['scalars']['gamma_depth']
   v=dict(state_id=m['state_id'],arm=arm,D=D,W=1,U=1,active_count=n,optimization_window=[m['scalars']['t0'],m['scalars']['t1']],geometry_before=geom0,geometry_after_native_fixed_initial_U=gn,geometry_after_native_updated_U=gn_u,geometry_after_clamp_fixed_initial_U=gc,mono_residual_sse_before=float(np.sum(mask*gap**2)),mono_residual_sse_after_native=float(np.sum(mask*gnp**2)),mono_residual_sse_after_clamp=float(np.sum(mask*gcp**2)),D1_prior_quadratic_before=float(alpha*np.sum(mask*gap**2)),D1_prior_quadratic_after_native=float(alpha*np.sum(mask*gnp**2)),D0_local_eta_step_damping=float(np.sum(eta*(dn[kx]-d0)**2)),disparity_delta=stats(dn[:n]-a['disps'][:n]),U_delta=stats(uc[:n]-a['U'][:n]),native_return_last_inner_dx=stats(np.load(out/'dx_last_inner.npy')),native_return_last_inner_dz=stats(np.load(out/'dz_last_inner.npy')),full_native_objective_available=False,normal_system_available=False,**{k:rec[k] for k in ['native_seconds','negative_disparities_native_active','clamp_affected_active','peak_allocated_bytes','peak_reserved_bytes']})
   new_json(output/f'{arm}_D{D}_NUMERIC_DIAGNOSTICS.json',v);metrics[D]=v
   with (output/f'{arm}_D{D}_EDGE_RESIDUALS.csv').open('w',newline='') as f:
    wr=csv.DictWriter(f,fieldnames=edges_after[0].keys());wr.writeheader();wr.writerows(edges_after)
  new_json(output/f'{arm}_INITIAL_STATE_DIAGNOSTICS.json',dict(state_id=m['state_id'],geometry=geom0,depth_support=int(mask.sum()),positive_depth_fraction=float(mask.mean()),eta=stats(eta),C_prior_positive=alpha,C_geometry=stats(C[kx]),b_prior=stats(-(mask*alpha*(d0-mono))),b_geometry=stats(b[kx]),diagnostic_scope='CPU_FLOAT64_INITIAL_LINEARIZATION_TERMS_NOT_CAPTURED_NATIVE_INTERNALS'))
 print(json.dumps({'analysis_complete':True,'states':2,'branches':4}))
if __name__=='__main__':
 start=__import__('time').monotonic();exitcode=0
 try:
  assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
  main()
 except Exception:
  exitcode=1
  __import__('traceback').print_exc()
 finally:
  new_json(pathlib.Path(sys.argv[2])/'ANALYSIS_PROCESS.json',dict(exit_code=exitcode,elapsed_seconds=__import__('time').monotonic()-start,torch_imported='torch' in sys.modules))
 sys.exit(exitcode)
