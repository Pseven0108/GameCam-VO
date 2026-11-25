"""One captured BA state: four C/G cells, two U modes, installed endpoint controls."""
import os,sys,pathlib,json,hashlib,time,traceback,argparse,gc
ROOT=pathlib.Path(__file__).resolve().parents[1];HIST=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
sys.path[:0]=[str(HIST/'source_candidate'),str(ROOT/'build_attempt02'),str(ROOT/'tools')]
TENSOR_NAMES=['poses','disps','intrinsics','selected_prior','targets','weights','uncertainties','temp_y_cdot','dino_feats_resize','affine_weights','eta','ii','jj']
SCALAR_NAMES=['t0','t1','iterations','lm','ep','gamma_data','gamma_prior','gamma_depth','lr','weight_decay','motion_only','depth_only','enable_update_uncer','enable_udba','enable_affine_transform','enable_bidirectional_uncer','debug']
TRACE_NAMES=['poses_before','disps_before','U_before','C_geometry','w_geometry','C','w','Q','E','kx','A','v','schur_subtraction','schur_rhs_subtraction','H_raw','rhs','L_damped_raw','dx','dz','poses_after','disps_after','U_after']
def main():
 import torch,numpy as np
 from native_control.snapshot import load_state
 from checkpoint.checkpoint_adapter import value_sha
 from checkpoint.rng_state import restore_rng_state
 import droid_backends
 import gamecam_task005b_depth_paths as candidate
 p=argparse.ArgumentParser();p.add_argument('--state',required=True);a=p.parse_args();name=a.state
 src=ROOT/'snapshots'/name;out=ROOT/'results_context02'/name;out.mkdir(exist_ok=False)
 torch.set_num_threads(2);torch.cuda.set_device(0)
 base,manifest=load_state(src,allow_cuda=True)
 assert manifest['provenance']['artifact_kind']=='TASK005B_REAL_BA_INPUT'
 assert base['scalars']['iterations']==2 and base['scalars']['enable_udba'] and base['scalars']['enable_update_uncer']
 assert not base['scalars']['enable_bidirectional_uncer'] and not base['scalars']['motion_only']
 template={**base['tensors'],'cached_mono':base['cached_mono']}
 baseline_hash={n:value_sha(v) for n,v in template.items()}
 baseline_meta={n:{'shape':list(v.shape),'stride':list(v.stride()),'offset':v.storage_offset(),'dtype':str(v.dtype),'device':str(v.device)} for n,v in template.items()}
 (out/'INPUT_IDENTITY.json').write_text(json.dumps({'state_sha256':manifest['state_sha256'],'provenance':manifest['provenance'],'tensor_value_sha256':baseline_hash,'tensor_metadata':baseline_meta,'scalars':base['scalars'],'slot_rgb_tokens':base['slot_rgb_tokens']},indent=2))
 def clone_input(U):
  stores={};copies={}
  for n,v in template.items():
   key=(str(v.device),v.untyped_storage()._cdata)
   if key not in stores:
    raw=torch.empty(0,dtype=torch.uint8,device=v.device).set_(v.untyped_storage(),0,(v.untyped_storage().nbytes(),),(1,)).clone()
    stores[key]=raw
   copies[n]=torch.empty(0,dtype=v.dtype,device=v.device).set_(stores[key].untyped_storage(),v.storage_offset(),v.shape,v.stride())
  actual={n:value_sha(v) for n,v in copies.items()}
  if actual!=baseline_hash:raise RuntimeError('Cloned full input SHA differs')
  # Enforce alias-equivalence classes as well as byte-value hashes.
  for n,v in template.items():
   for k,w in template.items():
    if (v.device==w.device and v.untyped_storage()._cdata==w.untyped_storage()._cdata)!=(copies[n].device==copies[k].device and copies[n].untyped_storage()._cdata==copies[k].untyped_storage()._cdata):raise RuntimeError('Input alias relation changed')
  scalars=dict(base['scalars']);scalars['enable_update_uncer']=U
  values=[copies[n] for n in TENSOR_NAMES]+[scalars[n] for n in SCALAR_NAMES]
  restore_rng_state(base['rng'])
  return copies,values,scalars,actual
 controls={};endpoints=[];summaries=[]
 # Original installed extension: exactly four controls for each captured context.
 for U in (False,True):
  for D in (1,0):
   tag=('NATIVE_UPDATE' if U else 'FROZEN')+'_D'+str(D);t=time.time();c,v,s,h=clone_input(U)
   v[3]=c['cached_mono'] if D else torch.zeros_like(c['selected_prior'])
   result=droid_backends.ba(*v);torch.cuda.synchronize()
   if len(result)!=2:raise RuntimeError('Installed native return signature changed')
   control={'dx_last':result[0].detach().cpu().clone(),'dz_last':result[1].detach().cpu().clone()}
   for n in ['poses','disps','uncertainties','temp_y_cdot','affine_weights']:control[n]=c[n].detach().cpu().clone()
   if any(not bool(torch.isfinite(z).all()) for z in control.values()):raise RuntimeError('Original control produced NaN/Inf')
   controls[(U,D)]=control
   np.savez_compressed(out/(tag+'_ORIGINAL.npz'),**{n:z.numpy() for n,z in control.items()})
   (out/(tag+'_ORIGINAL.receipt.json')).write_text(json.dumps({'native_call_kind':'installed_original_control','D':D,'U':U,'seconds':time.time()-t,'input_SHA_verified':True,'state_sha256':manifest['state_sha256'],'input_tensor_hashes':h,'scalars':s},indent=2))
   del c,v,result;gc.collect();torch.cuda.empty_cache()
   print(json.dumps({'event':'CONTROL_COMPLETE','state':name,'tag':tag}),flush=True)
 for U in (False,True):
  for cell,(C,G) in {'A':(1,1),'D':(0,0),'B':(1,0),'C':(0,1)}.items():
   tag=('NATIVE_UPDATE' if U else 'FROZEN')+'_'+cell;t=time.time();c,v,s,h=clone_input(U)
   v[3]=c['cached_mono']
   result=candidate.ba_paths(*v,bool(C),bool(G));torch.cuda.synchronize()
   if len(result)!=46:raise RuntimeError('Expected two iterations x22 native diagnostics plus final dx/dz')
   arrays={'last_dx':result[0].detach().cpu().numpy(),'last_dz':result[1].detach().cpu().numpy()}
   for it in range(2):
    for j,n in enumerate(TRACE_NAMES):arrays['iter'+str(it+1)+'_'+n]=result[2+it*22+j].detach().cpu().numpy()
   for n in ['poses','disps','uncertainties','temp_y_cdot','affine_weights']:arrays['final_'+n]=c[n].detach().cpu().numpy()
   if any(not np.isfinite(z).all() for z in arrays.values()):raise RuntimeError('Candidate native output NaN/Inf')
   equivalent=None
   if cell in ('A','D'):
    original=controls[(U,1 if cell=='A' else 0)];deltas={};ok=True
    for n in ['poses','disps','uncertainties','temp_y_cdot','affine_weights']:
     a0=arrays['final_'+n];b0=original[n].numpy();deltas[n]=float(np.max(np.abs(a0-b0))) if a0.size else 0.0
     ok=ok and np.allclose(a0,b0,atol=1e-6,rtol=1e-5,equal_nan=False)
    for n,key in [('dx_last','last_dx'),('dz_last','last_dz')]:
     d0=original[n].numpy();deltas[n]=float(np.max(np.abs(arrays[key]-d0))) if d0.size else 0.0
     ok=ok and np.allclose(arrays[key],d0,atol=1e-6,rtol=1e-5,equal_nan=False)
    equivalent={'PASS':bool(ok),'max_abs':deltas,'atol':1e-6,'rtol':1e-5};endpoints.append({'tag':tag,**equivalent})
    if not ok:
     np.savez_compressed(out/(tag+'_FAILED_ENDPOINT.npz'),**arrays)
     (out/'ENDPOINT_FAILURE.json').write_text(json.dumps({'tag':tag,**equivalent},indent=2));raise RuntimeError('Endpoint equivalence failed; do not loosen tolerance or retry')
   np.savez_compressed(out/(tag+'.npz'),**arrays)
   receipt={'state':name,'state_sha256':manifest['state_sha256'],'cell':cell,'C':C,'G':G,'U_native_update':U,'inner_iterations':2,'one_native_call':True,'seconds':time.time()-t,'input_SHA_verified':True,'input_tensor_hashes':h,'scalars':s,'endpoint_equivalence':equivalent,'postcall_clamp_applied':False}
   (out/(tag+'.receipt.json')).write_text(json.dumps(receipt,indent=2));summaries.append(receipt)
   del c,v,result,arrays;gc.collect();torch.cuda.empty_cache()
   print(json.dumps({'event':'CELL_COMPLETE','state':name,'tag':tag,'seconds':time.time()-t}),flush=True)
 # For independent common-weight nonlinear reprojection diagnostics, retain small actual inputs.
 np.savez_compressed(out/'COMMON_INPUTS.npz',poses=template['poses'].cpu().numpy(),disps=template['disps'].cpu().numpy(),intrinsics=template['intrinsics'].cpu().numpy(),targets=template['targets'].cpu().numpy(),weights=template['weights'].cpu().numpy(),uncertainties=template['uncertainties'].cpu().numpy(),mono=template['cached_mono'].cpu().numpy(),ii=template['ii'].cpu().numpy(),jj=template['jj'].cpu().numpy(),eta=template['eta'].cpu().numpy(),affine_weights=template['affine_weights'].cpu().numpy(),temp_y_cdot=template['temp_y_cdot'].cpu().numpy())
 (out/'SUCCESS.json').write_text(json.dumps({'state':name,'state_sha256':manifest['state_sha256'],'native_controls':4,'candidate_native_calls':8,'endpoint_checks':endpoints,'total_native_calls':12,'inner_iterations_per_call':2,'prefix_or_SLAM_rerun':False,'PASS':True},indent=2))
 print(json.dumps({'event':'STATE_REPLAY_COMPLETE','state':name,'native_calls':12}),flush=True)
if __name__=='__main__':
 try:
  import torch
  with torch.no_grad():main()
 except BaseException:traceback.print_exc();raise
