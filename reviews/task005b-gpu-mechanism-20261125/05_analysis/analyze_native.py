"""CPU diagnostics of native C/G/U traces. No GT depth or accuracy claims."""
import pathlib,sys,json,tarfile,io,csv,math,hashlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')
def load_archive(file):
 out={}
 with tarfile.open(file,'r:') as t:
  for m in t:
   if not m.isfile():continue
   n=m.name.removeprefix('./')
   if n.endswith('.npz'):
    with np.load(io.BytesIO(t.extractfile(m).read()),allow_pickle=False) as a:out[n]={k:a[k] for k in a.files}
   elif n.endswith('.json'):out[n]=json.load(t.extractfile(m))
 return out

def qmat(q):
 x,y,z,w=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]],dtype=np.float64)
def reprojection(poses,disps,ii,jj,K):
 h,w=disps.shape[-2:];yy,xx=np.mgrid[:h,:w];fx,fy,cx,cy=K;X=np.stack([(xx-cx)/fx,(yy-cy)/fy,np.ones_like(xx)],0).reshape(3,-1)
 pred=[];valid=[]
 for i,j in zip(ii,jj):
  i=int(i);j=int(j)
  if i==j:R=np.eye(3);T=np.array([-.1,0,0])
  else:
   Ri=qmat(poses[i,3:]);Rj=qmat(poses[j,3:]);R=Rj@Ri.T;T=poses[j,:3]-R@poses[i,:3]
  Y=R@X+T[:,None]*disps[i].reshape(1,-1);ok=(Y[2]>=.25)&np.isfinite(Y).all(0)
  z=np.where(ok,Y[2],1.);uv=np.stack([fx*Y[0]/z+cx,fy*Y[1]/z+cy],0).reshape(2,h,w)
  pred.append(uv);valid.append(ok.reshape(h,w))
 return np.array(pred),np.array(valid)
def sym_lower(M):return np.tril(M)+np.tril(M,-1).T
def spectrum(M):
 L=sym_lower(M);e=np.linalg.eigvalsh(L);s=np.linalg.svd(L,compute_uv=False);tol=max(L.shape)*np.finfo(float).eps*s[0] if len(s) else 0
 return {'lambda_min':float(e[0]),'lambda_max':float(e[-1]),'rank':int(np.sum(s>tol)),'dimension':len(s),'condition_2':float(s[0]/s[-1]) if s[-1]>tol else None,'SPD':bool(e[0]>0),'asymmetry_max':float(np.max(np.abs(M-M.T)))}
def write_csv(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (ROOT/'05_analysis'/name).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def analyze(archive):
 a=load_archive(archive);ident=a['INPUT_IDENTITY.json'];inputs=a['COMMON_INPUTS.npz'];state=ident['provenance'];sc=ident['scalars'];cells={k[:-4]:v for k,v in a.items() if k in [u+'_'+c+'.npz' for u in ['FROZEN','NATIVE_UPDATE'] for c in 'ABCD']}
 per=[];effects=[];feedback=[];consistency=[]
 init_pred,init_valid=reprojection(inputs['poses'],inputs['disps'],inputs['ii'],inputs['jj'],inputs['intrinsics'])
 gate=np.clip(1/np.maximum(45*inputs['uncertainties'][inputs['ii']]-35,.1),0,1)
 frozen_weights=.001*inputs['weights']*gate[:,None]
 for it in (1,2):
  pref='iter'+str(it)+'_';preds={};common=init_valid.copy()
  for tag,z in cells.items():
   pred,ok=reprojection(z[pref+'poses_after'],z[pref+'disps_after'],inputs['ii'],inputs['jj'],inputs['intrinsics']);preds[tag]=pred;common&=ok
  # Exactly the same support and weights for every C/G/U comparison at this iteration.
  support=common[:,None];initial_res=inputs['targets']-init_pred
  initial_loss=float(np.sum(frozen_weights*initial_res**2*support));denom=float(np.sum(frozen_weights*support))
  for tag,z in cells.items():
   C,G={'A':(1,1),'B':(1,0),'C':(0,1),'D':(0,0)}[tag[-1]];H=z[pref+'H_raw'];L=z[pref+'L_damped_raw'];rhs=z[pref+'rhs'];dx=z[pref+'dx'];dz=z[pref+'dz'];sp=spectrum(L);raw=spectrum(H)
   native_res=float(np.linalg.norm(sym_lower(L)@dx.reshape(-1)-rhs));rhs_norm=float(np.linalg.norm(rhs));res=inputs['targets']-preds[tag]
   loss=float(np.sum(frozen_weights*res**2*support))
   row={**{k:state[k] for k in ['arm','D_origin','schedule','rgb']},'U_mode':tag.rsplit('_',1)[0],'cell':tag[-1],'iteration':it,'C':C,'G':G,'dx_translation_norm':float(np.linalg.norm(dx[:,:3])),'dx_rotation_norm':float(np.linalg.norm(dx[:,3:])),'dz_norm':float(np.linalg.norm(dz)),'negative_disparities_after':int(np.sum(z[pref+'disps_after']<0)),'U_update_norm':float(np.linalg.norm(z[pref+'U_after']-z[pref+'U_before'])),'common_support_fraction':float(np.mean(common)),'common_weight_loss_before':initial_loss,'common_weight_loss_after':loss,'common_weight_loss_change':loss-initial_loss,'fixed_weight_pixel_RMSE':math.sqrt(loss/denom) if denom>0 else None,'native_linear_relative_residual':native_res/max(rhs_norm,1e-30),'L_condition_2':sp['condition_2'],'L_lambda_min':sp['lambda_min'],'L_lambda_max':sp['lambda_max'],'L_SPD':sp['SPD'],'L_rank':sp['rank'],'L_dimension':sp['dimension'],'L_asymmetry_max':sp['asymmetry_max'],'H_lambda_min':raw['lambda_min'],'H_condition_2':raw['condition_2']}
   per.append(row)
  for U in ['FROZEN','NATIVE_UPDATE']:
   v={c:cells[U+'_'+c][pref+'dx'].astype(np.float64) for c in 'ABCD'}
   ce=v['B']-v['D'];ge=v['C']-v['D'];inter=v['A']-v['B']-v['C']+v['D'];tot=v['A']-v['D']
   factors={'curvature':ce,'gradient':ge,'interaction':inter,'total':tot}
   for name,vec in factors.items():effects.append({**{k:state[k] for k in ['arm','D_origin','schedule','rgb']},'U_mode':U,'iteration':it,'contrast':name,'translation_vector_norm':float(np.linalg.norm(vec[:,:3])),'rotation_vector_norm':float(np.linalg.norm(vec[:,3:])),'signed_translation_projection_on_total':float(np.sum(vec[:,:3]*tot[:,:3])/max(np.sum(tot[:,:3]**2),1e-30)),'closure_residual':float(np.linalg.norm(tot-ce-ge-inter))})
   for c,g in [('A','B'),('C','D')]:
    x=cells[U+'_'+c];y=cells[U+'_'+g];M=sym_lower(x[pref+'L_damped_raw']);db=x[pref+'rhs']-y[pref+'rhs'];diff=x[pref+'dx']-y[pref+'dx']
    pred=np.linalg.solve(M,db).reshape(diff.shape)
    consistency.append({**{k:state[k] for k in ['arm','schedule','rgb']},'U_mode':U,'iteration':it,'comparison':c+'-'+g,'H_max_difference':float(np.max(np.abs(x[pref+'H_raw']-y[pref+'H_raw']))),'L_max_difference':float(np.max(np.abs(x[pref+'L_damped_raw']-y[pref+'L_damped_raw']))),'predicted_gradient_dx_error_norm':float(np.linalg.norm(pred-diff)),'fixed_linearization_identity_expected':it==1})
  for c in 'ABCD':
   x=cells['NATIVE_UPDATE_'+c];y=cells['FROZEN_'+c]
   feedback.append({**{k:state[k] for k in ['arm','schedule','rgb']},'cell':c,'iteration':it,'native_minus_frozen_dx_translation_norm':float(np.linalg.norm(x[pref+'dx'][:,:3]-y[pref+'dx'][:,:3])),'native_minus_frozen_dx_rotation_norm':float(np.linalg.norm(x[pref+'dx'][:,3:]-y[pref+'dx'][:,3:])),'native_minus_frozen_U_after_norm':float(np.linalg.norm(x[pref+'U_after']-y[pref+'U_after'])),'affine_after_total_difference':float(np.linalg.norm(x['final_affine_weights']-y['final_affine_weights']))})
 return per,effects,feedback,consistency
if __name__=='__main__':
 all_rows=[[],[],[],[]]
 for file in sorted(RECEIVER.glob('result_*.tar')):
  rows=analyze(file)
  for a,b in zip(all_rows,rows):a.extend(b)
 for n,r in zip(['NATIVE_ITERATION_METRICS.csv','VECTOR_PATH_CONTRASTS.csv','U_FEEDBACK_CONTRASTS.csv','GRADIENT_IDENTITY_CHECKS.csv'],all_rows):write_csv(n,r)
 print(json.dumps({'archives':len(list(RECEIVER.glob('result_*.tar'))),'row_counts':[len(x) for x in all_rows]}))
