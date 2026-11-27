"""Reproduce frozen evidence, run all fixed fusions, and describe VIPER transfer."""
from common import *
from fusion_math import *
import argparse,datetime,time
from scipy.ndimage import label

VIEWS=['FROZEN_BICUBIC_ZERO_EXTENDED','R2_2_BILINEAR_SAME_FOCAL']

def stats(a):
    a=np.asarray(a,dtype=float)
    return {'min':float(a.min()),'max':float(a.max()),'mean':float(a.mean()),'SD':float(a.std()),**{'P'+str(i):float(np.percentile(a,i)) for i in [5,25,50,75,95,99]}}

def agreement(n,f,error=None):
    nh=n>=.8;fh=f>=.8;both=nh&fh;only_n=nh&~fh;only_f=fh&~nh
    out={'native_flip_spearman':correlation(n,f),'both_high_fraction':float(both.mean()),'native_only_high_fraction':float(only_n.mean()),'flip_only_high_fraction':float(only_f.mean()),'XOR_high_fraction':float((nh^fh).mean()),'high_low_conflict_fraction':float(((nh&(f<=.2))|(fh&(n<=.2))).mean()),'both_low_fraction':float(((n<=.2)&(f<=.2)).mean()),'top20_intersection_over_union':float(both.sum()/(nh|fh).sum()) if (nh|fh).any() else None}
    if error is not None:
        for name,mask in [('both_high',both),('native_only_high',only_n),('flip_only_high',only_f),('neither_high',~(nh|fh))]:
            out[name+'_pixels']=int(mask.sum());out[name+'_error_gt02_rate']=float((error[mask]>.2).mean()) if mask.any() else None;out[name+'_mean_AbsRel']=float(error[mask].mean()) if mask.any() else None
    return out

def spatial(score):
    high=score>=np.quantile(score,.8);cc,k=label(high,structure=np.ones((3,3),int));sizes=np.bincount(cc.ravel())[1:]
    total=int(high.sum())
    return {'top20_actual_fraction':float(high.mean()),'connected_components_8':int(k),'largest_component_fraction_of_high':float(sizes.max()/total) if total else None,'component_HHI':float(np.sum((sizes/total)**2)) if total else None}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',default='cpu_001');a=p.parse_args()
    out=TASK/'runs'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();old=legacy();allrows=records();mvs=[r for r in allrows if r['sample']['dataset']=='MVS-Synth']
    core=[Path(__file__),TASK/'scripts/common.py',TASK/'scripts/fusion_math.py',TASK/'scripts/prepare_intake.py']
    codehash={p.name:sha(p) for p in core}
    dump(out/'RUN_CONFIGURATION.json',{'protocol_sha256':sha(TASK/'PROTOCOL_FROZEN.json'),'source_sha256':codehash,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_GPU_forwards':0,'ranks_use_GT_mask':False,'models_fitted_on_sequence0000_only':True})
    metric_rows=[];curves=[];riskbins=[];probrows=[];probbins=[];regrows=[];modelrows=[];agreement_rows=[];viperrows=[];rawrows=[];repro=[];scales={};errorrows=[]
    expected={(r['sample_id'],r['signal']):r for r in csvread(HIST/'CONDITIONAL_NATIVE_UNIT_METRICS.csv')}
    for view in VIEWS:
        contexts=[]
        for row in mvs:
            pred,conf,flip,flipped=maps(row,view)
            methods,n,f=scores(conf,flip)
            gt=ground_truth(row);valid=np.isfinite(gt)&(gt>0)
            if pred.shape!=gt.shape or not valid.any():raise RuntimeError('GT admission mismatch')
            if (pred[valid]<0).any():raise RuntimeError('Negative prediction, preserve failure')
            contexts.append({'row':row,'prediction':pred,'gt':gt,'valid':valid,'methods':methods,'n':n,'f':f,'flipped':flipped})
        calibration=[r for r in contexts if r['row']['sample']['sequence_id']=='0000']
        evaluation=[r for r in contexts if r['row']['sample']['sequence_id']=='0001']
        if len(calibration)!=3 or len(evaluation)!=3:raise RuntimeError('Frozen sequence split changed')
        if any((r['prediction'][r['valid']]<=0).any() for r in calibration):raise RuntimeError('Scale fit domain invalid')
        scale=float(np.exp(np.median(np.concatenate([np.log(r['gt'][r['valid']])-np.log(r['prediction'][r['valid']]) for r in calibration]))));scales[view]=scale
        if view==VIEWS[0] and not np.isclose(scale,15.985507037495662,rtol=0,atol=1e-10):raise RuntimeError('Historical scale did not reproduce')
        for r in contexts:
            row=r['row'];item=row['sample'];sid=item['sample_id'];valid=r['valid'];gt=r['gt'];pred=r['prediction'];role='CALIBRATION' if item['sequence_id']=='0000' else 'PREVIOUSLY_OBSERVED_EVALUATION'
            error=np.abs(pred[valid]*scale-gt[valid])/(gt[valid]+1e-12);error_map=np.full(gt.shape,np.nan);error_map[valid]=error;r['error']=error;r['error_map']=error_map
            meta={'sample_id':sid,'sequence':item['sequence_id'],'role':role,'view':view}
            errorrows.append({**meta,'GT_valid_pixels':int(valid.sum()),'zero_predictions_retained':int((pred[valid]==0).sum()),'AbsRel_mean':float(error.mean()),'high_error_prevalence_gt02':float((error>.2).mean()),'scale':scale})
            agreement_rows.append({**meta,**agreement(r['n'][valid],r['f'][valid],error)})
            for method,s in r['methods'].items():
                risk=s[valid];rc=old.fast_rc(error,risk);br=old.binary_ranking(error>.2,risk)
                result={**meta,'method':method,'valid_pixels':len(error),'AUROC':br['AUROC'],'AP':br['AUPRC'],'AUSE':rc['AUSE'],'Spearman':correlation(error,risk),'AURG':rc['AURG'],'AbsRel_mean':float(error.mean())}
                metric_rows.append(result)
                if view==VIEWS[0] and method in ['NativeOnly','FlipOnly']:
                    signal='NativeConfidence' if method=='NativeOnly' else 'FlipRelative';prior=expected[sid,signal]
                    for key,prior_key in [('AUROC','AUROC_gt_0.2'),('AP','AUPRC_AP_gt_0.2'),('AUSE','AUSE_raw_AbsRel'),('Spearman','Spearman_error_vs_risk')]:
                        diff=abs(result[key]-float(prior[prior_key]));repro.append({'sample_id':sid,'signal':signal,'metric':key,'historical':float(prior[prior_key]),'recomputed':result[key],'absolute_difference':diff,'atol':1e-10,'pass':diff<=1e-10})
                        if diff>1e-10:raise RuntimeError('Historical metric mismatch: '+sid+' '+key)
                if role=='PREVIOUSLY_OBSERVED_EVALUATION' and method in CORE:
                    for i in np.unique(np.r_[0,np.linspace(1,len(error),201).astype(int)]):curves.append({**meta,'method':method,'coverage':float(rc['coverage'][i]),'risk':float(rc['risk'][i]),'oracle':float(rc['oracle'][i]),'random':float(rc['random'][i])})
                    rank=percentile(s)[valid]
                    bins=np.minimum((rank*10).astype(int),9)
                    for j in np.unique(bins):
                        own=bins==j;riskbins.append({**meta,'method':method,'risk_percentile_bin':int(j),'pixels':int(own.sum()),'mean_score':float(risk[own].mean()),'mean_AbsRel':float(error[own].mean()),'event_rate_gt02':float((error[own]>.2).mean())})
            if view==VIEWS[0]:
                arraypath=out/'risk_maps'/(sid+'.npz');arraypath.parent.mkdir(exist_ok=True)
                np.savez_compressed(arraypath,rank_native=r['n'],rank_flip=r['f'],risk_fusion=r['methods']['RankFusion'],risk_max=r['methods']['MaxFusion'],valid_GT=valid,AbsRel=error_map)
            print('MVS_SCORED',view,sid,flush=True)
        for method in METHODS:
            chunks=[]
            for r in calibration:
                mask=np.zeros(r['valid'].shape,bool);mask[::8,::8]=r['valid'][::8,::8]
                chunks.append((r['methods'][method][mask],r['error_map'][mask]))
            x=np.concatenate([t[0] for t in chunks]);e=np.concatenate([t[1] for t in chunks]);y=(e>.2).astype(float)
            model=fit_logistic(x,y);regression,regmodel=fit_regression(x,e)
            modelrows.append({'view':view,'method':method,'probability':model,'AbsRel_regression':regmodel})
            for r in evaluation:
                meta={'sample_id':r['row']['sample']['sample_id'],'sequence':'0001','view':view,'method':method};risk=r['methods'][method][r['valid']];error=r['error'];truth=error>.2
                probabilities,logits=logistic_predict(risk,model);pm,pb=probability_metrics(probabilities,logits,truth)
                probrows.append({**meta,**pm,'calibration_sequence':'0000','fresh_independent_test':False})
                for b in pb:probbins.append({**meta,**b})
                regrows.append({**meta,**error_metrics(regression.predict(risk),error),'calibration_sequence':'0000','fresh_independent_test':False})
                if method=='NativeOnly':
                    constant=model['calibration_prevalence'];v=np.full(error.shape,np.log(constant/(1-constant)));pr=np.full(error.shape,constant)
                    cm,_=probability_metrics(pr,v,truth);probrows.append({**meta,'method':'CalibrationPrevalence',**cm,'calibration_sequence':'0000','fresh_independent_test':False})
                    for name,c in [('CalibrationMeanAbsRel',float(e.mean())),('CalibrationMedianAbsRel',float(np.median(e)))]:regrows.append({**meta,'method':name,**error_metrics(np.full(error.shape,c),error),'calibration_sequence':'0000','fresh_independent_test':False})
        for row in allrows:
            item=row['sample']
            if item['dataset']!='VIPER':continue
            sid=item['sample_id'];pred,conf,flip,flipped=maps(row,view);methods,n,f=scores(conf,flip)
            meta={'sample_id':sid,'sequence':item['sequence_id'],'environment':item['environment'],'view':view,'dense_GT_available':False}
            agreement_rows.append({**meta,**agreement(n,f)})
            rawrows.append({**meta,'pixels':conf.size,'native_zero_depth':int((pred==0).sum()),'flip_zero_depth':int((flipped==0).sum()),'raw_confidence_negative_fraction':float((conf<0).mean()),'raw_confidence_ge1_fraction':float((conf>=1).mean()),**{'confidence_'+k:v for k,v in stats(conf).items()},**{'flip_'+k:v for k,v in stats(flip).items()}})
            for method,s in methods.items():
                if method not in CORE:continue
                display=n if method=='NativeOnly' else f if method=='FlipOnly' else s
                viperrows.append({**meta,'method':method,**stats(display),**spatial(display)})
            if view==VIEWS[0]:
                np.savez_compressed(out/'risk_maps'/(sid+'.npz'),rank_native=n,rank_flip=f,risk_fusion=methods['RankFusion'],risk_max=methods['MaxFusion'])
            print('VIPER_DESCRIBED',view,sid,flush=True)
    summaries=[]
    for view in VIEWS:
        for method in METHODS:
            own=[r for r in metric_rows if r['view']==view and r['method']==method and r['role']=='PREVIOUSLY_OBSERVED_EVALUATION']
            s={'view':view,'method':method,'evaluation_sequences':1,'frames':3,'aggregation':'equal-frame macro; no pixel-IID significance'}
            for key in ['AUROC','AP','AUSE','Spearman','AURG','AbsRel_mean']:
                values=np.array([r[key] for r in own]);s[key]=float(values.mean());s[key+'_SD_across_frames']=float(values.std(ddof=1));s[key+'_min']=float(values.min());s[key+'_max']=float(values.max())
            summaries.append(s)
    paired=[]
    for row in metric_rows:
        if row['role']!='PREVIOUSLY_OBSERVED_EVALUATION' or row['method'] not in ['RankFusion','MaxFusion','RankW25','RankW75']:continue
        for base in ['NativeOnly','FlipOnly']:
            other=next(r for r in metric_rows if r['sample_id']==row['sample_id'] and r['view']==row['view'] and r['method']==base)
            paired.append({k:row[k] for k in ['sample_id','sequence','view','method']}|{'compared_to':base}|{k+'_difference':row[k]-other[k] for k in ['AUROC','AP','AUSE','Spearman']})
    for name,rows in [('metrics_per_frame.csv',metric_rows),('metrics_summary.csv',summaries),('fusion_comparison.csv',paired),('risk_coverage.csv',curves),('risk_error_bins.csv',riskbins),('probability_metrics.csv',probrows),('probability_reliability_bins.csv',probbins),('regression_metrics.csv',regrows),('signal_complementarity.csv',agreement_rows),('viper_signal_statistics.csv',viperrows),('viper_raw_signal_statistics.csv',rawrows),('historical_reproduction.csv',repro),('depth_error_context.csv',errorrows)]:csvwrite(out/name,rows)
    dump(out/'CALIBRATION_MODELS.json',{'models':modelrows,'all_fit_sequence':'0000','all_evaluation_sequence':'0001','evaluation_used_for_fit':False})
    dump(out/'SCALES_AND_STATUS.json',{'scales':scales,'historical_metric_reproduction_all_pass':all(r['pass'] for r in repro),'strict_legacy_gate':'FAILED_AND_NOT_RELABELED','risk_fusion_new_model_forwards':0,'VIPER_error_accuracy_calibration':'NOT_EVALUATED_NO_ADMITTED_DENSE_GT','MVS_physical_depth_unit':'NOT_CERTIFIED','fresh_independent_test':False,'elapsed_CPU_seconds':time.perf_counter()-started,'no_PyTorch_import':'torch' not in sys.modules})
    cpu_assert();dump(TASK/'private/LATEST_SUCCESSFUL_RUN.json',{'path':str(out),'status':'COMPLETE'});print('CPU_EXPERIMENT_COMPLETE',str(out),flush=True)

if __name__=='__main__':main()
