"""Summaries use images as units; do not manufacture independent pixel samples."""
from common import *
from fusion_math import CORE

def main():
    run=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path'])
    raw=csvread(run/'viper_raw_signal_statistics.csv');agreements=csvread(run/'signal_complementarity.csv')
    weather=[]
    for view in ['FROZEN_BICUBIC_ZERO_EXTENDED','R2_2_BILINEAR_SAME_FOCAL']:
        for env in ['Day','Sunset','Rain','Snow','Night']:
            own=[r for r in raw if r['environment']==env and r['view']==view]
            agreement=[r for r in agreements if r.get('environment')==env and r['view']==view]
            line={'view':view,'environment':env,'sampled_frames':len(own),'independent_environment_instances':None,'temporal_stability_certified':False,'dense_depth_accuracy_certified':False}
            for key in ['confidence_mean','confidence_P50','confidence_P5','confidence_P95','flip_mean','flip_P50','flip_P95','raw_confidence_negative_fraction','raw_confidence_ge1_fraction']:
                v=np.array([float(r[key]) for r in own]);line[key]=float(v.mean());line[key+'_frame_min']=float(v.min());line[key+'_frame_max']=float(v.max())
            for key in ['native_flip_spearman','XOR_high_fraction','high_low_conflict_fraction','top20_intersection_over_union']:
                line[key]=float(np.mean([float(r[key]) for r in agreement]))
            weather.append(line)
    csvwrite(run/'viper_weather_macro.csv',weather)
    macro=csvread(run/'metrics_summary.csv');pairs=csvread(run/'fusion_comparison.csv')
    deltas=[]
    for view in dict.fromkeys(r['view'] for r in pairs):
        for method in ['RankFusion','MaxFusion','RankW25','RankW75']:
            for baseline in ['NativeOnly','FlipOnly']:
                own=[r for r in pairs if r['view']==view and r['method']==method and r['compared_to']==baseline]
                line={'view':view,'method':method,'compared_to':baseline,'frames':len(own),'independent_sequences':1,'test_is_new_unseen':False}
                for metric in ['AUROC','AP','AUSE','Spearman']:
                    d=np.array([float(r[metric+'_difference']) for r in own]);line[metric+'_delta_mean']=float(d.mean());line[metric+'_delta_min']=float(d.min());line[metric+'_delta_max']=float(d.max());line[metric+'_frame_wins']=int((d<0).sum() if metric=='AUSE' else (d>0).sum())
                deltas.append(line)
    csvwrite(run/'fusion_macro_differences.csv',deltas)
    extra=[]
    for filename,keys in [('probability_metrics.csv',['Brier','NLL','ECE10']),('regression_metrics.csv',['AbsRel_prediction_MAE','AbsRel_prediction_RMSE'])]:
        rows=csvread(run/filename)
        for view in dict.fromkeys(r['view'] for r in rows):
            for method in dict.fromkeys(r['method'] for r in rows):
                own=[r for r in rows if r['view']==view and r['method']==method]
                line={'analysis':filename[:-4],'view':view,'method':method,'frames':len(own),'independent_sequences':1}
                for k in keys:
                    values=np.array([float(r[k]) for r in own]);line[k]=float(values.mean());line[k+'_SD_across_frames']=float(values.std(ddof=1))
                extra.append(line)
    csvwrite(run/'calibration_macro.csv',extra)
    reproduction=csvread(run/'historical_reproduction.csv')
    indices={r['sample']['sample_id']:r for r in records()}
    dump(run/'DATA_SCOPE_SUMMARY.json',{'VIPER_frames':10,'VIPER_predicted_grid_pixels':sum(int(np.prod(r['sample']['input_hw'])) for r in indices.values() if r['sample']['dataset']=='VIPER'),'VIPER_environments':5,'MVS_calibration_frames':3,'MVS_evaluation_frames':3,'MVS_evaluation_sequences':1,'MVS_original_GT_dtype':'float16 raw EXR converted to float64 for arithmetic','historical_value_comparisons':len(reproduction),'historical_max_abs_metric_difference':max(float(r['absolute_difference']) for r in reproduction),'new_model_GPU_forwards':0,'new_dataset_download_bytes':0,'reader_dependency_install_not_model_install':True,'rank_normalization_uses_GT':False,'raw_rank_scores_are_probabilities':False,'weather_samples_are_not_a_temporal_continuity_study':True})
    print('FRAME-LEVEL MACROS COMPLETE')
    for r in weather:
        if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED':print(r['environment'],'raw_C_mean',r['confidence_mean'],'TTA_P95',r['flip_P95'],'rho',r['native_flip_spearman'],'conflict',r['high_low_conflict_fraction'])

if __name__=='__main__':main()
