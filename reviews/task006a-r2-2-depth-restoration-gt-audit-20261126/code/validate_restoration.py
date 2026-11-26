"""Cross-check independent float64 interpolation against native CPU torch outputs."""
import time
from common import *

def main():
    cpu_only();start=time.perf_counter();base=ROOT/'02_restoration/torch_CPU'
    receipt=json.loads((base/'CPU_RESTORE_RECEIPT.json').read_text('utf-8'))
    assert receipt['device']=='cpu' and receipt['model_forwards']==0
    cpurows={r['sample_id']:r for r in receipt['results']};rows=[];focals=[];fixtures=[]
    with np.load(base/'CPU_INTERPOLATION_FIXTURES.npz',allow_pickle=False) as f:
        for item in receipt['fixtures']:
            i=item['id'];mine=resize_bilinear(f[f'input_{i}'],item['output_shape']);theirs=f[f'output_{i}']
            ok=np.allclose(mine,theirs,rtol=2e-5,atol=2e-5)
            fixtures.append({**item,'max_abs_diff':float(np.max(np.abs(mine-theirs))),'allclose':bool(ok)})
            if not ok: raise RuntimeError('Independent interpolation fixture failed')
    for row in records():
        sid=row['sample']['sample_id'];cr=cpurows[sid];p=base/(sid+'.npz')
        if cr['sha256']!=sha(p):raise RuntimeError('CPU output changed')
        item=row['sample'];ih,iw=item['input_hw'];sh,sw=item['source_hw'];rh,rw=row['resized_hw'];l,t,r,b=row['padding_ltrb']
        fx=item['fx'];raw_fx=item['source_fx'];nominal=row['resize_scale']
        if abs(raw_fx*(iw/sw)-fx)>1e-8:raise RuntimeError('Input focal does not match source-to-input resize')
        focals.append({'sample_id':sid,'source_H':sh,'source_W':sw,'tracker_input_H':ih,'tracker_input_W':iw,
          'canonical_H':616,'canonical_W':1064,'resized_H':rh,'resized_W':rw,'padding_l':l,'padding_t':t,'padding_r':r,'padding_b':b,
          'source_fx':raw_fx,'input_fx':fx,'baseline_depth_factor':fx/1000.,'official_depth_factor':fx*nominal/1000.,
          'official_over_baseline_ratio':nominal,'actual_resize_sx':rw/iw,'actual_resize_sy':rh/ih,
          'nominal_scale_minus_actual_sy':nominal-rh/ih,
          'focal_invariance_source_vs_input_paths_abs':abs(raw_fx*(rw/sw)-fx*(rw/iw)),
          'source_grid_requires_new_model_inference':False,'GT_unit_established':False})
        with np.load(row['local_npz'],allow_pickle=False) as old,np.load(p,allow_pickle=False) as new:
            for mode in ['native','flip']:
                a=old[mode+'_canonical_depth'];mine64=restore_bilinear(a,row)*fx/1000.
                mine=restore_bilinear_float32(a,row)*np.float32(fx/1000.)
                theirs=new[mode+'_bilinear_same_focal_unclipped'];delta=np.abs(mine-theirs)
                ok=bool(np.allclose(mine,theirs,atol=3e-4,rtol=3e-5))
                if not ok:raise RuntimeError('Real float64/torch CPU interpolation mismatch')
                oldraw=old[mode+'_depth_unclipped'];oldclip=old[mode+'_depth'];fixed=new[mode+'_bilinear_same_focal']
                if not np.isfinite(fixed).all() or (fixed<=0).any():raise RuntimeError('Positive network output did not restore strictly positive')
                cubicreplay=[x for x in cr['comparisons'] if x['mode']==mode][0]
                cdelta=np.abs(new[mode+'_confidence_CPU'].astype(float)-old[mode+'_confidence'].astype(float))
                rr={'sample_id':sid,'dataset':item['dataset'],'environment':item['environment'],'mode':mode,
                  'pixel_count':int(fixed.size),'canonical_min':float(a.min()),'canonical_nonpositive':int((a<=0).sum()),
                  'old_bicubic_unclipped_min':float(oldraw.min()),'old_bicubic_negative':int((oldraw<0).sum()),
                  'old_clamped_zero':int((oldclip==0).sum()),'old_upper_clamp_300':int((oldraw>300).sum()),
                  'bilinear_min':float(fixed.min()),'bilinear_nonpositive':int((fixed<=0).sum()),
                  'bilinear_upper_clamp_300':int((theirs>300).sum()),
                  'bilinear_float32_vs_torch_CPU_max_abs':float(delta.max()),'bilinear_float32_vs_torch_CPU_allclose':ok,
                  'analytic_float64_vs_torch_CPU_max_abs':float(np.abs(mine64-theirs).max()),
                  'confidence_replay_max_abs':float(cdelta.max()),
                  **{k:v for k,v in cubicreplay.items() if k.startswith('bicubic_CPU_vs_saved_GPU')}}
                if item['dataset']=='MVS-Synth':
                    g=depth(gt_dir(item['sequence_id'])/'depths'/(item['frame_id']+'.exr'));v=np.isfinite(g)&(g>0)
                    rr.update(valid_GT_pixels=int(v.sum()),old_zero_on_valid_GT=int(((oldclip==0)&v).sum()),new_nonpositive_on_valid_GT=int(((fixed<=0)&v).sum()))
                rows.append(rr)
        print('RESTORE_VALIDATED',sid,flush=True)
    csvwrite(ROOT/'02_restoration/RESTORATION_COMPARISON.csv',rows)
    csvwrite(ROOT/'02_restoration/FOCAL_AND_GRID_TRANSFORM_AUDIT.csv',focals)
    dump(ROOT/'02_restoration/INTERPOLATION_INDEPENDENT_VALIDATION.json',{'fixtures':fixtures,'all_real_maps_native_dtype_reconstruction_pass':True,
      'rtol':3e-5,'atol':3e-4,'fixture_rtol':2e-5,'fixture_atol':2e-5,'geometry':'Pixel-center, align_corners=False, non-antialiased bilinear, edge extension',
      'initial_float64_vs_float32_failure_preserved':'INITIAL_FLOAT64_VS_FLOAT32_VALIDATION_FAILURE.json',
      'standards_relaxed':False,'fix':'Match original float32 source-coordinate and lambda arithmetic; retain float64 analytic comparison',
      'exact_bitwise_GPU_equivalence_claim':False,'torch_CPU_interpolation_context_only':True,'no_model_inference':True})
    summary={'unique_RGB':16,'native_and_flip_maps':32,'old_bicubic_negative_all_maps':sum(r['old_bicubic_negative'] for r in rows),
      'old_clamped_zero_all_maps':sum(r['old_clamped_zero'] for r in rows),'new_nonpositive_all_maps':sum(r['bilinear_nonpositive'] for r in rows),
      'old_native_MVS_zero_on_valid_GT':sum(r.get('old_zero_on_valid_GT',0) for r in rows if r['mode']=='native'),
      'new_native_MVS_nonpositive_on_valid_GT':sum(r.get('new_nonpositive_on_valid_GT',0) for r in rows if r['mode']=='native'),
      'float32_vs_torch_CPU_max_abs':max(r['bilinear_float32_vs_torch_CPU_max_abs'] for r in rows),
      'elapsed_CPU_seconds':time.perf_counter()-start,'algorithm_production_source_changed':False,
      'repair_scope':'Independent depth evaluator restore function; production DROID-W unchanged'}
    dump(ROOT/'02_restoration/RESTORATION_SUMMARY.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
