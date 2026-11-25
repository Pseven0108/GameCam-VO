"""Bounded R2: same real state; each call keeps two native internal iterations."""
import os,sys,pathlib,json,hashlib,time,gc,argparse,traceback,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
HIST=ROOT.parent/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE'
sys.path[:0]=[str(HIST/'source_candidate'),str(OLD/'build_attempt02'),str(OLD/'tools'),str(ROOT/'build')]
TENSORS=['poses','disps','intrinsics','selected_prior','targets','weights','uncertainties','temp_y_cdot','dino_feats_resize','affine_weights','eta','ii','jj']
SCALARS=['t0','t1','iterations','lm','ep','gamma_data','gamma_prior','gamma_depth','lr','weight_decay','motion_only','depth_only','enable_update_uncer','enable_udba','enable_affine_transform','enable_bidirectional_uncer','debug']
OLD_TRACE=['poses_before','disps_before','U_before','C_geometry','w_geometry','C','w','Q','E','kx','A','v','schur_subtraction','schur_rhs_subtraction','H_raw','rhs','L_damped_raw','dx','dz','poses_after','disps_after','U_after']
def file_sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def main():
 import torch,numpy as np
 from native_control.snapshot import load_state
 from checkpoint.checkpoint_adapter import value_sha
 from checkpoint.rng_state import restore_rng_state
 import droid_backends,gamecam_task005b_depth_paths as existing
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['plain','trace'],required=True);args=p.parse_args()
 out=ROOT/'results'/args.phase;out.mkdir(parents=True,exist_ok=False)
 assert file_sha(droid_backends.__file__)=='6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e'
 assert file_sha(existing.__file__)=='1edb9685e1569f2513a4dc895b2eddbe699e15d2d684079e4d9c2f77e9a4ad44'
 torch.set_num_threads(2);torch.cuda.set_device(0)
 base,manifest=load_state(OLD/'snapshots/D0_S1_RGB233',allow_cuda=True)
 assert manifest['provenance']['artifact_kind']=='TASK005B_REAL_BA_INPUT'
 assert manifest['provenance']['arm']=='D0_S1' if 'arm' in manifest['provenance'] else True
 s=base['scalars'];assert s['iterations']==2 and s['enable_update_uncer'] and s['enable_udba'] and s['enable_affine_transform']
 assert not any(s[k] for k in ['motion_only','depth_only','debug','enable_bidirectional_uncer'])
 template={**base['tensors'],'cached_mono':base['cached_mono']}
 hashes={k:value_sha(v) for k,v in template.items()}
 def metadata(v):return {'shape':list(v.shape),'stride':list(v.stride()),'offset':v.storage_offset(),'dtype':str(v.dtype),'device':str(v.device)}
 meta={k:metadata(v) for k,v in template.items()}
 identity={'state_sha256':manifest['state_sha256'],'manifest_file_sha256':file_sha(OLD/'snapshots/D0_S1_RGB233/manifest.json'),'provenance':manifest['provenance'],'tensor_value_SHA':hashes,'metadata':meta,'scalars':s,'original_module':str(droid_backends.__file__),'existing_module':str(existing.__file__),'torch':torch.__version__,'cuda':torch.version.cuda,'no_grad':not torch.is_grad_enabled()}
 (out/'INPUT_IDENTITY.json').write_text(json.dumps(identity,indent=2)+'\n')
 def clone():
  stores={};c={}
  for n,v in template.items():
   key=(str(v.device),v.untyped_storage()._cdata)
   if key not in stores:stores[key]=torch.empty(0,dtype=torch.uint8,device=v.device).set_(v.untyped_storage(),0,(v.untyped_storage().nbytes(),),(1,)).clone()
   c[n]=torch.empty(0,dtype=v.dtype,device=v.device).set_(stores[key].untyped_storage(),v.storage_offset(),v.shape,v.stride())
  assert {k:value_sha(v) for k,v in c.items()}==hashes
  assert {k:metadata(v) for k,v in c.items()}==meta
  for n,v in template.items():
   for k,w in template.items():assert (v.device==w.device and v.untyped_storage()._cdata==w.untyped_storage()._cdata)==(c[n].device==c[k].device and c[n].untyped_storage()._cdata==c[k].untyped_storage()._cdata)
  restore_rng_state(base['rng'])
  return c
 if args.phase=='plain':plan=[('original',droid_backends.ba),('reference',existing.ba_reference),('paths',existing.ba_paths)]
 else:
  import gamecam_task005b_r2_observer as observed
  plan=[('trace_reference',observed.ba_trace_reference),('trace_paths',observed.ba_trace_paths)]
 trace_names=json.loads((ROOT/'candidate/TRACE_SCHEMA.json').read_text()) if args.phase=='trace' else OLD_TRACE
 for label,fn in plan:
  for rep in (1,2):
   tag=f'{label}_{rep}';assert shutil.disk_usage(ROOT).free>10*1024**3+192*1024**2
   c=clone();values=[c[n] for n in TENSORS]+[s[n] for n in SCALARS]
   is_paths=label.endswith('paths')
   values[3]=c['cached_mono'] if is_paths else torch.zeros_like(c['selected_prior'])
   effective={n:value_sha(v) for n,v in zip(TENSORS,values)}
   call={'tag':tag,'kind':label,'replicate':rep,'state_sha256':manifest['state_sha256'],'cloned_tensor_hashes':hashes,'effective_tensor_hashes':effective,'metadata_and_alias_verified':True,'rng_restored':True,'scalars':s,'two_iterations_in_one_native_call':True,'postcall_clamp':False,'D':0,'C':0,'G':0,'U_native_update':True,'started_unix':time.time()}
   (out/(tag+'.STARTED.json')).write_text(json.dumps(call,indent=2)+'\n')
   print(json.dumps({'event':'CALL_START','tag':tag}),flush=True)
   torch.cuda.reset_peak_memory_stats()
   result=fn(*values,False,False) if is_paths else fn(*values)
   torch.cuda.synchronize()
   arrays={'dx_last':result[0].detach().cpu().numpy(),'dz_last':result[1].detach().cpu().numpy()}
   for n in ['poses','disps','uncertainties','temp_y_cdot','affine_weights']:arrays[n]=c[n].detach().cpu().numpy()
   if label!='original' and label!='reference':
    assert len(result)==2+2*len(trace_names),(len(result),trace_names)
    for it in range(2):
     for j,n in enumerate(trace_names):arrays[f'iter{it+1}_{n}']=result[2+it*len(trace_names)+j].detach().cpu().numpy()
   assert all(np.isfinite(v).all() for v in arrays.values()),'Nonfinite native output; stop'
   path=out/(tag+'.npz');np.savez_compressed(path,**arrays)
   call.update(seconds=time.time()-call['started_unix'],complete=True,all_finite=True,array_count=len(arrays),gpu_allocated_peak_bytes=torch.cuda.max_memory_allocated(),gpu_reserved_peak_bytes=torch.cuda.max_memory_reserved(),output_bytes=path.stat().st_size,output_sha256=file_sha(path),native_function=fn.__name__)
   (out/(tag+'.receipt.json')).write_text(json.dumps(call,indent=2)+'\n')
   print(json.dumps({'event':'CALL_COMPLETE','tag':tag,'seconds':call['seconds'],'output_bytes':call['output_bytes']}),flush=True)
   del c,values,result,arrays;gc.collect();torch.cuda.empty_cache()
 assert {k:value_sha(v) for k,v in template.items()}==hashes
 (out/'COMPLETE.json').write_text(json.dumps({'calls':2*len(plan),'input_preserved':True,'iterations_per_call':2,'phase':args.phase,'all_finite':True},indent=2)+'\n')
if __name__=='__main__':
 try:
  import torch
  with torch.no_grad():main()
 except BaseException:traceback.print_exc();raise
