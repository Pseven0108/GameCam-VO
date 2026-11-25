"""Single sealed context. Two isolated native kernels and U-only paired BA controls."""
import os,sys,pathlib,json,time,hashlib,gc,shutil,traceback
ROOT=pathlib.Path(__file__).resolve().parents[1]
R1=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
R2=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
HIST=ROOT.parent/'DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE'
sys.path[:0]=[str(HIST/'source_candidate'),str(R1/'tools'),str(ROOT/'build')]
TENSORS=['poses','disps','intrinsics','selected_prior','targets','weights','uncertainties','temp_y_cdot','dino_feats_resize','affine_weights','eta','ii','jj']
SCALARS=['t0','t1','iterations','lm','ep','gamma_data','gamma_prior','gamma_depth','lr','weight_decay','motion_only','depth_only','enable_update_uncer','enable_udba','enable_affine_transform','enable_bidirectional_uncer','debug']
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def save_json(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
    import torch,numpy as np
    from native_control.snapshot import load_state
    from checkpoint.checkpoint_adapter import value_sha
    from checkpoint.rng_state import restore_rng_state
    import droid_backends,gamecam_task005b_r3_isolation as module
    out=ROOT/'results';out.mkdir(exist_ok=False)
    assert sha(droid_backends.__file__)=='6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e'
    assert sha(module.__file__)==json.loads((ROOT/'build/BUILD_COMPLETE.json').read_text())['sha256']
    torch.set_num_threads(2);torch.cuda.set_device(0)
    base,manifest=load_state(R1/'snapshots/D0_S1_RGB233',allow_cuda=True)
    assert manifest['state_sha256']=='90f436de0f6139dc013fd545aeb047fe0ed28b649a6d2e811f8e15fbfa35b791'
    s=base['scalars'];assert s['iterations']==2 and s['enable_update_uncer'] and s['enable_udba'] and s['enable_affine_transform']
    assert not any(s[n] for n in ['motion_only','depth_only','enable_bidirectional_uncer','debug'])
    template={**base['tensors'],'cached_mono':base['cached_mono']}
    hashes={k:value_sha(v) for k,v in template.items()}
    def meta(v):return {'shape':list(v.shape),'stride':list(v.stride()),'offset':v.storage_offset(),'dtype':str(v.dtype),'device':str(v.device)}
    metadata={k:meta(v) for k,v in template.items()}
    r2path=R2/'results/trace/trace_reference_1.npz'
    assert sha(r2path)=='05425393e11cfb025a2b2e95234809e1f4b11ef39e29fe658d8f1912bf64b7b5'
    with np.load(r2path,allow_pickle=False) as z:
        sealed={k:torch.from_numpy(z[k].copy()).to('cuda') for k in ['iter1_poses_after_geometry','iter1_disps_after_geometry','iter1_U_before_linear','iter1_J_total','iter1_temp_before_linear','iter1_kx']}
    identity={'snapshot_state_sha256':manifest['state_sha256'],'R2_trace_SHA':sha(r2path),'template_value_SHA':hashes,'metadata':metadata,'scalars':s,'R2_intermediate_value_SHA':{k:value_sha(v) for k,v in sealed.items()},'torch':torch.__version__,'cuda':torch.version.cuda,'extension_SHA':sha(module.__file__),'original_SHA':sha(droid_backends.__file__),'no_grad':not torch.is_grad_enabled(),'isolated_repeats_each':16,'BA_calls':20,'internal_iterations_each':2,'same_process_independent_state_clones':True}
    save_json(out/'INPUT_IDENTITY.json',identity)
    def room():assert shutil.disk_usage(ROOT).free>10*1024**3+64*1024**2,'Disk reserve violated'
    def persist(tag,arrays,receipt):
        room();assert all(np.isfinite(v).all() for v in arrays.values()),'Nonfinite output: stop'
        path=out/(tag+'.npz');np.savez_compressed(path,**arrays)
        receipt.update(complete=True,all_finite=True,array_count=len(arrays),output_bytes=path.stat().st_size,output_SHA=sha(path),seconds=time.time()-receipt['started_unix'])
        save_json(out/(tag+'.receipt.json'),receipt)
        print(json.dumps({'event':'COMPLETE','tag':tag,'seconds':receipt['seconds'],'bytes':receipt['output_bytes']}),flush=True)
    # These contexts are independent. No Jjj output is used by the linear experiment.
    jargs=[template['targets'],sealed['iter1_U_before_linear'],template['dino_feats_resize'],sealed['iter1_poses_after_geometry'],sealed['iter1_disps_after_geometry'],template['intrinsics'],template['ii'],template['jj']]
    largs=[sealed['iter1_J_total'],template['dino_feats_resize'],sealed['iter1_U_before_linear'],sealed['iter1_temp_before_linear'],sealed['iter1_kx']]
    isolations=[('jjj',module.isolated_jjj,jargs,['Jii_data','Jjj_data','kf_count']),('linear',module.isolated_linear,largs,['J_linear'])]
    for label,fn,arguments,names in isolations:
        expected=[value_sha(v) for v in arguments]
        save_json(out/(label+'_INPUT.json'),{'hashes':expected,'metadata':[meta(v) for v in arguments],'from_fixed_R2_trace':'trace_reference_1.npz/iter1','upstream_r3_results_used':False})
        for rep in range(1,17):
            tag=f'{label}_{rep:02d}';room();assert [value_sha(v) for v in arguments]==expected
            restore_rng_state(base['rng'])
            receipt={'tag':tag,'kind':label,'replicate':rep,'input_SHA':expected,'started_unix':time.time(),'output_initialized_zero':True}
            save_json(out/(tag+'.STARTED.json'),receipt);print(json.dumps({'event':'START','tag':tag}),flush=True)
            values=fn(*arguments,s['t1']) if label=='jjj' else fn(*arguments)
            torch.cuda.synchronize();arrays={n:v.detach().cpu().numpy() for n,v in zip(names,values)}
            assert [value_sha(v) for v in arguments]==expected
            persist(tag,arrays,receipt);del values,arrays
    def clone():
        stores={};c={}
        for n,v in template.items():
            key=(str(v.device),v.untyped_storage()._cdata)
            if key not in stores:stores[key]=torch.empty(0,dtype=torch.uint8,device=v.device).set_(v.untyped_storage(),0,(v.untyped_storage().nbytes(),),(1,)).clone()
            c[n]=torch.empty(0,dtype=v.dtype,device=v.device).set_(stores[key].untyped_storage(),v.storage_offset(),v.shape,v.stride())
        assert {k:value_sha(v) for k,v in c.items()}==hashes
        assert {k:meta(v) for k,v in c.items()}==metadata
        for n,v in template.items():
            for k,w in template.items():assert (v.device==w.device and v.untyped_storage()._cdata==w.untyped_storage()._cdata)==(c[n].device==c[k].device and c[n].untyped_storage()._cdata==c[k].untyped_storage()._cdata)
        restore_rng_state(base['rng']);return c
    names=json.loads((ROOT/'candidate/TRACE_SCHEMA.json').read_text())
    plan=[('original_native',droid_backends.ba,False,False),('reference_native',module.ba_reference,False,False),('paths_native',module.ba_paths,True,False),('reference_fixed',module.ba_reference,False,True),('paths_fixed',module.ba_paths,True,True)]
    calls=0
    for label,fn,is_paths,freeze in plan:
        for rep in range(1,5):
            room();tag=f'{label}_{rep:02d}';c=clone()
            args=[c[n] for n in TENSORS]+[s[n] for n in SCALARS]
            args[3]=c['cached_mono'] if is_paths else torch.zeros_like(c['selected_prior'])
            receipt={'tag':tag,'kind':label,'replicate':rep,'started_unix':time.time(),'cloned_tensor_SHA':hashes,'effective_tensor_SHA':{n:value_sha(v) for n,v in zip(TENSORS,args)},'alias_metadata_verified':True,'RNG_restored':True,'two_internal_iterations':True,'C':0,'G':0,'freeze_U_only':freeze,'affine_temp_update_enabled':True,'postcall_clamp':False}
            save_json(out/(tag+'.STARTED.json'),receipt);print(json.dumps({'event':'START','tag':tag}),flush=True)
            torch.cuda.reset_peak_memory_stats()
            if label=='original_native':result=fn(*args)
            elif is_paths:result=fn(*args,False,False,freeze)
            else:result=fn(*args,freeze)
            torch.cuda.synchronize()
            arrays={'dx_last':result[0].detach().cpu().numpy(),'dz_last':result[1].detach().cpu().numpy()}
            for n in ['poses','disps','uncertainties','temp_y_cdot','affine_weights']:arrays[n]=c[n].detach().cpu().numpy()
            if label!='original_native':
                assert len(result)==2+2*len(names)
                for it in range(2):
                    for j,n in enumerate(names):arrays[f'iter{it+1}_{n}']=result[2+it*len(names)+j].detach().cpu().numpy()
            if freeze:
                assert np.array_equal(arrays['uncertainties'],template['uncertainties'].cpu().numpy())
                for it in (1,2):assert np.array_equal(arrays[f'iter{it}_U_after'],arrays['iter1_U_before'])
            receipt['gpu_peak_allocated_bytes']=torch.cuda.max_memory_allocated();receipt['gpu_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
            persist(tag,arrays,receipt);calls+=1
            del c,args,result,arrays;gc.collect();torch.cuda.empty_cache()
    assert calls==20 and {k:value_sha(v) for k,v in template.items()}==hashes
    save_json(out/'COMPLETE.json',{'isolated_jjj_calls':16,'isolated_linear_calls':16,'two_iteration_BA_calls':calls,'all_finite':True,'input_preserved':True,'no_full_sequence_or_model':True})
if __name__=='__main__':
    try:
        import torch
        with torch.no_grad():main()
    except BaseException:traceback.print_exc();raise
