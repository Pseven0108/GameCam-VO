"""Seal method choices and audit existing source caches before new fusion scoring."""
from common import *
import datetime,importlib.metadata as metadata,platform,shutil

def main():
    intake=TASK/'intake';intake.mkdir(exist_ok=True)
    code=intake/'legacy_code';code.mkdir(exist_ok=True)
    evidence=[]
    for name in ['evaluate_pilot.py','reliability_metrics.py']:
        p=SOURCE/'experiments/scripts'/name
        shutil.copyfile(p,code/name);evidence.append(p)
    for name in ['EVALUATION_PREREGISTRATION.json','DIAGNOSTIC_ZERO_EXTENSION_AMENDMENT.json']:
        p=SOURCE/'experiments/configs'/name;shutil.copyfile(p,intake/name);evidence.append(p)
    for name in ['CONDITIONAL_TEST_MACRO.csv','CONDITIONAL_NATIVE_UNIT_METRICS.csv','CALIBRATION_ONLY_DEPTH_SCALE.json','CONDITIONAL_DEPTH_ERRORS.csv']:
        p=HIST/name;shutil.copyfile(p,intake/name);evidence.append(p)
    fields=['sample_id','dataset','sequence_id','frame_id','environment','input_hw','source_hw','fx']
    rows=[];audit=[];protected=[]
    for rel in ['01_smoke/smoke_qualified','02_pilot/pilot']:
        folder=SOURCE/rel;receipt=folder/'INFERENCE_RECEIPT.json';evidence.append(receipt)
        original=json.loads(receipt.read_text(encoding='utf-8'));assert original['status']=='PASS'
        for row in original['results']:
            item=row['sample'];path=folder/Path(row['output']).name
            assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
            row['local_npz']=str(path);rows.append(row);evidence.append(path)
            rgb=SOURCE/'inputs/VIPER'/(item['sample_id']+'.jpg') if item['dataset']=='VIPER' else (Path('D:/aaa/GameCam-VO/data/mvs_synth/GTAV_540')/item['sequence_id'] if item['sequence_id']=='0000' else SOURCE/'inputs/MVS-Synth/GTAV_540/0001')/'images'/(item['frame_id']+'.png')
            assert sha(rgb)==item['rgb_sha256'];row['local_rgb']=str(rgb);evidence.append(rgb)
            with np.load(path,allow_pickle=False) as z:
                for name in ['native_depth','native_confidence','flip_depth','flip_relative_disagreement','tta_valid']:
                    a=z[name]
                    audit.append({**{k:item.get(k) for k in fields},'cache':str(path.relative_to(SOURCE)),'field':name,'shape':'x'.join(map(str,a.shape)),'dtype':str(a.dtype),'pixels':a.size,'finite':int(np.isfinite(a).sum()),'zero_count':int((a==0).sum()),'sha256':row['sha256']})
            repaired=RESTORED/'02_restoration/torch_CPU'/(item['sample_id']+'.npz')
            if not repaired.exists():raise RuntimeError('Existing sensitivity cache missing')
            evidence.append(repaired)
            if item['dataset']=='MVS-Synth':
                pair=json.loads((HIST/(item['sample_id']+'_GT_PAIRING.json')).read_text())
                gt=Path(pair['GT_path']);assert sha(gt)==pair['GT_sha256'];evidence.append(gt)
    assert len(rows)==16 and sum(x['sample']['dataset']=='VIPER' for x in rows)==10
    dump(TASK/'private/ASSET_INDEX.json',{'records':rows})
    csvwrite(TASK/'results/asset_field_inventory.csv',audit)
    for path in sorted(set(evidence)):
        s=path.stat();protected.append({'path':str(path),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':sha(path)})
    # Track production source/config identities without importing them.
    baseline=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
    for rel in ['src/depth_video.py','src/factor_graph.py','src/lib/droid_kernels.cu','src/lib/droid.cpp','configs/droid_w.yaml']:
        p=baseline/rel
        if p.exists():
            s=p.stat();protected.append({'path':str(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':sha(p)})
    dump(TASK/'private/PROTECTED_INPUTS_BEFORE.json',protected)
    public=[dict(path=Path(r['path']).name,bytes=r['bytes'],sha256=r['sha256']) for r in protected]
    dump(TASK/'intake/SOURCE_CACHE_IDENTITIES.json',public)
    protocol={'status':'FROZEN_BEFORE_NEW_FUSION_METRICS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'task':'TASK011A','target_dataset':'VIPER','MVS_usage':'Explicitly authorized existing-cache auxiliary diagnostic only','calibration_sequence':'0000','previously_observed_evaluation_sequence':'0001','frames':['0000','0049','0099'],'fresh_independent_test':False,'primary_view':'FROZEN_BICUBIC_ZERO_EXTENDED','sensitivity_view':'R2_2_BILINEAR_SAME_FOCAL','scale':'exp(median(log(GT)-log(pred))) on all finite-positive Calibration0000 GT pixels, one scale per restoration view','GT_mask':'finite strictly positive raw EXR; no prediction-dependent mask','zero_depth_policy':'Retain finite nonnegative depths, zero error=1 in AbsRel; strict original GT gate remains failed','AbsRel':'abs(scale*pred-GT)/(GT+1e-12)','high_error_event':'AbsRel > 0.2','native_risk':'negative uncalibrated native confidence','flip_risk':'abs(native_depth-reverse_x(flip_depth))/(abs(native_depth)+1e-6)','percentile':'(average_rank - 0.5)/number_of_finite_pixels, separately for each signal and image, over the entire predicted grid before reading GT; not normalized over GT-valid mask','primary_fusion_weight_native':0.5,'sensitivity_weights_native':[0.25,0.75],'max_fusion':'max(rank_native,rank_flip)','ranking_metrics':'frozen original AUROC / AP / tie-averaged raw AbsRel AUSE / Spearman','aggregation':'Equal-frame macro; single evaluation sequence; no pixel-iid CI or generalization claim','regression':'one-dimensional increasing isotonic AbsRel map per method, calibration stride8 GT-valid grid only, evaluate all valid sequence0001 pixels; constant calibration mean/median baselines','probability_mapping':'one-dimensional nonnegative-slope logistic per method, same calibration stride8 grid, no test refit; constant calibration prevalence baseline','probability_scores':'Brier, stable-logit NLL, ECE10 equal-width bins','VIPER_GT_metrics':False,'VIPER_spatial_high_risk':'per-method image q80 threshold including ties; record actual fraction; 8-connected component size/HHI','agreement':'native and flip percentile >=0.8 / <=0.2; XOR high-risk disagreement and high-versus-low conflicts','new_model_forwards':0,'BA_or_CADP_integration':False,'no_selection_or_tuning_on_evaluation_scores':True}
    dump(TASK/'PROTOCOL_FROZEN.json',protocol)
    dump(TASK/'results/ENVIRONMENT.json',{'python':platform.python_version(),'executable':sys.executable,'OS':platform.platform(),'CPU_only':True,'packages':{n:metadata.version(n) for n in ['numpy','scipy','scikit-learn','matplotlib','Pillow']},'OpenEXR':{'version':'3.3.3','isolated_current_Python_wheel':True,'historical_cp39_reader_incompatible_with_current_cp311':True},'original_environment_modified':False,'historical_environment_scope':'Original R2.1 CPU environment differed; exact metric reproduction is independently checked'})
    cpu_assert();print('ASSETS_ADMITTED',len(rows),'protected_files',len(protected),'protocol',sha(TASK/'PROTOCOL_FROZEN.json'),flush=True)

if __name__=='__main__':main()
