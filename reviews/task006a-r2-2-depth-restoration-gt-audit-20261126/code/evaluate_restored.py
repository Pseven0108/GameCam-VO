"""Paired audit of old outputs and isolated restoration variants.

Sequence0001 is previously observed. These are descriptive native-unit audit
results, not a fresh held-out performance test or a physical meter benchmark.
"""
import time
from scipy.ndimage import sobel,label
from scipy.stats import spearmanr
from common import *
sys.path.insert(0,str(PREV/'experiments/scripts'))
from reliability_metrics import binary_ranking

VARIANTS=['R2_1_BICUBIC_FROZEN','BILINEAR_SAME_FOCAL','BILINEAR_OFFICIAL_RESIZED_FOCAL']
HISTORICAL_SCALE=15.985507037495662

def load(row):
    p=row['sample'];d=gt_dir(p['sequence_id']);g=depth(d/'depths'/(p['frame_id']+'.exr'))
    valid=np.isfinite(g)&(g>0)
    with np.load(row['local_npz'],allow_pickle=False) as a,np.load(ROOT/'02_restoration/torch_CPU'/(p['sample_id']+'.npz'),allow_pickle=False) as b:
        pairs={
          VARIANTS[0]:(a['native_depth'].astype(float),a['flip_depth'][:,::-1].astype(float)),
          VARIANTS[1]:(b['native_bilinear_same_focal'].astype(float),b['flip_bilinear_same_focal'][:,::-1].astype(float)),
          VARIANTS[2]:(b['native_bilinear_official_focal'].astype(float),b['flip_bilinear_official_focal'][:,::-1].astype(float))}
        c=a['native_confidence'].astype(float)
        # Initial entropy remains a secondary audit signal; it is not promoted
        # or sign-flipped after its inverse association in R2.1.
        ent=resize_bilinear(a['native_bin_entropy'],row['canonical_hw'])
        ent=restore_bilinear(ent,row)
    if c.shape!=g.shape:raise RuntimeError('GT grid differs')
    return {'row':row,'gt':g,'valid':valid,'pairs':pairs,'confidence':c,'entropy':ent}

def mask_components(mask,error):
    cc,n=label(mask,structure=np.ones((3,3),int))
    if not n:return cc.astype('int32'),[]
    sizes=np.bincount(cc.ravel())[1:]
    ids=np.argsort(-sizes,kind='stable')[:10]+1
    rows=[]
    for i in ids:
        yy,xx=np.nonzero(cc==i)
        rows.append({'component':int(i),'pixels':len(yy),'bbox_xmin':int(xx.min()),'bbox_xmax':int(xx.max()),
          'bbox_ymin':int(yy.min()),'bbox_ymax':int(yy.max()),'mean_error':float(error[yy,xx].mean()),'max_error':float(error[yy,xx].max())})
    return cc.astype('int32'),rows

def rank(errors,risk):
    if not np.isfinite(errors).all() or not np.isfinite(risk).all():raise ValueError('Do not filter invalid predictions/signals')
    out={}
    for event,truth in [('gt_0_2',errors>.2),('ge_1_0',errors>=1.)]:
        r=binary_ranking(truth,risk)
        out.update({event+'_AUROC':r['AUROC'],event+'_AP':r['AUPRC'],event+'_prevalence':float(truth.mean())})
    out['Spearman_error_risk']=float(spearmanr(errors,risk).statistic) if np.ptp(risk)>0 and np.ptp(errors)>0 else None
    return out

def main():
    cpu_only();started=time.perf_counter()
    allrows=[r for r in records() if r['sample']['dataset']=='MVS-Synth'];rr=[load(r) for r in allrows]
    cal=[r for r in rr if r['row']['sample']['sequence_id']=='0000']
    assert len(cal)==3
    cv=np.concatenate([r['confidence'][r['valid']] for r in cal]);confidence_q=np.quantile(cv,[.25,.5,.75])
    distance=np.quantile(np.concatenate([r['gt'][r['valid']] for r in cal]),[1/3,2/3])
    edges=np.r_[-np.inf,np.unique(np.quantile(cv,np.linspace(0,1,11)[1:-1])),np.inf]
    scales={}
    for variant in VARIANTS:
        chunks=[]
        for r in cal:
            p=r['pairs'][variant][0][r['valid']]
            if not np.isfinite(p).all() or (p<=0).any():raise RuntimeError('Calibration contains invalid predictions; no filtering allowed')
            chunks.append(np.log(r['gt'][r['valid']])-np.log(p))
        scales[variant]=float(np.exp(np.median(np.concatenate(chunks))))
    if not np.isclose(scales[VARIANTS[0]],HISTORICAL_SCALE,rtol=1e-13):raise RuntimeError('Frozen baseline scale did not reproduce')
    dump(ROOT/'04_evaluation/CALIBRATION_ONLY_SCALES.json',{'per_variant_native_unit_scale':scales,'historical_frozen_scale':HISTORICAL_SCALE,
      'fit_sequence':'0000','fit_frames':['0000','0049','0099'],'formula':'exp(median(log(GT)-log(pred)))',
      'observed_audit_sequence':'0001','audit_is_fresh_test':False,'probability_fit_performed':False,
      'confidence_Q25_Q50_Q75':confidence_q.tolist(),'distance_terciles_native':distance.tolist(),
      'no_unit_conversion_claim':True,'thresholds_fit_to_observed_sequence':False})
    metrics=[];risks=[];strata=[];bins=[];components=[];zeroevents=[];coords=[];sensitivity=[]
    arraysout=ROOT/'04_evaluation/pixel_maps';arraysout.mkdir(exist_ok=False)
    for r in rr:
        item=r['row']['sample'];sid=item['sample_id'];g=r['gt'];v=r['valid'];c=r['confidence'];h,w=g.shape
        yy,xx=np.indices(g.shape);border=(xx<.05*w)|(xx>=.95*w)|(yy<.05*h)|(yy>=.95*h)
        finiteg=np.where(v,g,0);grad=np.hypot(sobel(finiteg,axis=0),sobel(finiteg,axis=1))/(np.where(v,g,1)+1e-12)
        regions={'all_valid':v,'near_native':v&(g<=distance[0]),'middle_native':v&(g>distance[0])&(g<=distance[1]),
                 'far_native':v&(g>distance[1]),'border_5pct':v&border,'interior':v&~border,
                 'depth_boundary_proxy':v&(grad>.05),'nonboundary_proxy':v&(grad<=.05),
                 'high_raw_confidence_cal_Q75':v&(c>=confidence_q[2]),'low_raw_confidence_cal_Q25':v&(c<=confidence_q[0])}
        pixel_arrays={'valid_GT':v,'confidence_raw':c.astype('float32'),'depth_boundary_proxy':v&(grad>.05)}
        for vi,variant in enumerate(VARIANTS):
            p,flip=r['pairs'][variant]
            if not np.isfinite(p[v]).all() or (p[v]<0).any():raise RuntimeError('Negative/nonfinite prediction; no masking')
            scaled=p*scales[variant];error=np.full(g.shape,np.nan);error[v]=np.abs(scaled[v]-g[v])/g[v]
            e=error[v];severe=v&(error>=1.);higher=v&(error>.2);reliable=v&(error<=.2)
            with np.errstate(divide='ignore'):logerr=np.abs(np.log(scaled[v])-np.log(g[v]))
            cc,comp=mask_components(severe,error)
            for cp in comp:components.append({'sample_id':sid,'variant':variant,**cp})
            line={'sample_id':sid,'sequence':item['sequence_id'],'role':'CALIBRATION_AUDIT' if item['sequence_id']=='0000' else 'PREVIOUSLY_OBSERVED_AUDIT',
              'variant':variant,'GT_valid_pixels':int(v.sum()),'scale':scales[variant],
              'AbsRel_mean':float(e.mean()),'AbsRel_median':float(np.median(e)),'AbsRel_P90':float(np.quantile(e,.9)),
              'AbsRel_P95':float(np.quantile(e,.95)),'AbsRel_P99':float(np.quantile(e,.99)),
              'AbsLog_mean':float(logerr.mean()) if np.isfinite(logerr).all() else None,'AbsLog_infinite_count':int(np.isinf(logerr).sum()),
              'zero_prediction_on_valid_GT':int((p[v]==0).sum()),'fraction_error_gt_0_2':float((e>.2).mean()),
              'severe_error_ge_1_count':int(severe.sum()),'severe_error_ge_1_fraction':float(severe.sum()/v.sum()),
              'reliable_le_0_2_count':int(reliable.sum()),'uncertain_gt_0_2_lt_1_count':int((v&(error>.2)&(error<1)).sum()),
              'severe_connected_components':int(cc.max()),'physical_meters_certified':False,'fresh_test':False}
            metrics.append(line)
            sensitivity.append({'sample_id':sid,'variant':variant,'fixed_R2_1_scale':HISTORICAL_SCALE,
              'AbsRel_at_fixed_R2_1_scale':float(np.mean(np.abs(p[v]*HISTORICAL_SCALE-g[v])/g[v])),
              'AbsRel_at_own_calibration_scale':float(e.mean()),'not_a_physical_scale_accuracy_claim':True})
            signals={'NativeConfidence':-c,'FlipRelative':np.abs(p-flip)/(np.abs(p)+1e-6),'InitialBinEntropy':r['entropy']}
            for name,s in signals.items():
                risks.append({'sample_id':sid,'sequence':item['sequence_id'],'variant':variant,'signal':name,**rank(e,s[v]),'previously_observed':True})
            for name,m in regions.items():
                count=int(m.sum())
                if count:
                    strata.append({'sample_id':sid,'variant':variant,'region':name,'GT_valid_pixels':count,
                        'AbsRel_mean':float(error[m].mean()),'severe_count':int((severe&m).sum()),
                        'severe_fraction':float((severe&m).sum()/count),'fraction_error_gt_0_2':float((error[m]>.2).mean()),
                        'raw_confidence_median':float(np.median(c[m]))})
            for bi in range(len(edges)-1):
                m=v&(c>=edges[bi])&(c<edges[bi+1])
                if m.any(): bins.append({'sample_id':sid,'variant':variant,'confidence_bin_from_calibration':bi,
                     'raw_confidence_min':float(c[m].min()),'raw_confidence_max':float(c[m].max()),'pixels':int(m.sum()),
                     'AbsRel_mean':float(error[m].mean()),'severe_fraction':float((error[m]>=1).mean()),'error_gt_0_2_fraction':float((error[m]>.2).mean())})
            pixel_arrays[f'v{vi}_AbsRel']=error.astype('float32')
            pixel_arrays[f'v{vi}_prediction_scaled_native']=scaled.astype('float32')
            pixel_arrays[f'v{vi}_severe_ge_1']=severe
            pixel_arrays[f'v{vi}_severe_components']=cc
            if vi==0:
                zy,zx=np.nonzero(v&(p==0))
                for y,x in zip(zy,zx):
                    zeroevents.append({'sample_id':sid,'y':int(y),'x':int(x),'GT_native':float(g[y,x]),'old_depth':0.,'raw_confidence':float(c[y,x]),
                        'bilinear_same_focal_depth':float(r['pairs'][VARIANTS[1]][0][y,x]),
                        'bilinear_same_focal_AbsRel':float(abs(r['pairs'][VARIANTS[1]][0][y,x]*scales[VARIANTS[1]]-g[y,x])/g[y,x])})
            # Bounded, deterministic source-data table for direct error/confidence
            # inspection. Full-resolution maps above contain every valid pixel.
            samplemask=np.zeros(v.shape,bool);samplemask[::16,::16]=v[::16,::16]
            for y,x in zip(*np.nonzero(samplemask)):
                coords.append({'sample_id':sid,'variant':variant,'y':int(y),'x':int(x),'GT_native':float(g[y,x]),
                  'depth_scaled_native':float(scaled[y,x]),'AbsRel':float(error[y,x]),'raw_confidence':float(c[y,x]),'severe_ge_1':bool(severe[y,x])})
        np.savez_compressed(arraysout/(sid+'.npz'),**pixel_arrays)
        print('EVALUATED',sid,flush=True)
    for name,data in [('PAIRED_DEPTH_ERROR_METRICS',metrics),('CONFIDENCE_AND_TTA_RANKING',risks),('SPATIAL_ERROR_STRATA',strata),
                      ('CONFIDENCE_ERROR_BINS',bins),('SEVERE_ERROR_COMPONENTS_TOP10',components),('ORIGINAL_SEVEN_ZERO_PIXELS',zeroevents),
                      ('PIXEL_ERROR_CONFIDENCE_SAMPLED',coords),('FOCAL_FIXED_SCALE_SENSITIVITY',sensitivity)]:
        csvwrite(ROOT/'04_evaluation'/(name+'.csv'),data)
    macro=[]
    for sequence in ['0000','0001']:
        for variant in VARIANTS:
            sub=[r for r in metrics if r['sequence']==sequence and r['variant']==variant]
            macro.append({'sequence':sequence,'variant':variant,'frames':3,'aggregation':'Equal frame mean; no pixel-iid inference',
               **{key:float(np.mean([r[key] for r in sub])) for key in ['AbsRel_mean','AbsRel_median','fraction_error_gt_0_2','severe_error_ge_1_fraction']},
               'zero_predictions':sum(r['zero_prediction_on_valid_GT'] for r in sub),'physical_meter_claim':False,'fresh_test':False})
    csvwrite(ROOT/'04_evaluation/DEPTH_ERROR_MACRO.csv',macro)
    dump(ROOT/'04_evaluation/EVALUATION_STATUS.json',{'status':'PAIRED_RESTORATION_AUDIT_COMPLETE','GT_frames':6,'variants':VARIANTS,
      'new_model_forwards':0,'new_probability_models':0,'severe_threshold':'>=1.0','all_valid_GT_pixels_retained':True,
      'physical_metric_GT':'BLOCKED_UNKNOWN_UNIT','test0001':'PREVIOUSLY_OBSERVED_NOT_FRESH_TEST',
      'next_stage_requires_new_unseen_test_sequence':True,'elapsed_CPU_seconds':time.perf_counter()-started,
      'confidence_claim_scope':'Raw-score conditional diagnostics; no calibrated probability claim','macros':macro})
    print(json.dumps(macro,indent=2))

if __name__=='__main__':main()
