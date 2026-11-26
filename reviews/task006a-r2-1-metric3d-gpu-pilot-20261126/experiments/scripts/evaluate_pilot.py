"""Real-output diagnostics plus explicitly scale-calibrated native-unit GT analysis.

Physical metric accuracy remains BLOCKED. No SLAM-derived depth, network training,
test-set scale fitting, or probability interpretation of the raw confidence.
"""
import argparse,csv,hashlib,json,os,pathlib,sys,time
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates,sobel
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import spearmanr,pearsonr
from reliability_metrics import GTAdmission,depth_errors,binary_ranking,reliability_bins,probability_calibration,depth_bin_statistics
ROOT=pathlib.Path(__file__).resolve().parents[2]
PREVIOUS=ROOT.parent/'task006a-r2-depth-prior-reliability-20261126'
sys.path.insert(0,str(PREVIOUS/'experiments/runtime_site'))
import OpenEXR

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(path,obj):
 with path.open('x',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvwrite(path,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with path.open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def resize_linear(a,shape):
 a=np.asarray(a,dtype=np.float64);h,w=shape
 yy=(np.arange(h)+.5)*a.shape[0]/h-.5;xx=(np.arange(w)+.5)*a.shape[1]/w-.5
 return map_coordinates(a,np.array(np.meshgrid(yy,xx,indexing='ij')),order=1,mode='nearest',prefilter=False)
def restore_bin(a,row):
 canonical=resize_linear(a,(616,1064));l,t,r,b=row['padding_ltrb']
 return resize_linear(canonical[t:616-b,l:1064-r],row['sample']['input_hw'])
def fast_rc(errors,risk):
 e=np.asarray(errors,dtype=float);s=np.asarray(risk,dtype=float)
 if e.ndim!=1 or s.shape!=e.shape or not len(e) or not np.isfinite(e).all() or not np.isfinite(s).all() or (e<0).any():raise ValueError('Invalid error/risk vectors')
 order=np.argsort(s,kind='stable');ee=e[order];ss=s[order];n=len(e)
 starts=np.r_[0,np.flatnonzero(ss[1:]!=ss[:-1])+1];ends=np.r_[starts[1:],n]
 counts=ends-starts;sums=np.add.reduceat(ee,starts);means=sums/counts
 before=np.r_[0,np.cumsum(sums)[:-1]]
 prefix=np.repeat(before,counts)+(np.arange(n)-np.repeat(starts,counts)+1)*np.repeat(means,counts)
 coverage=np.r_[0,np.arange(1,n+1)/n];curve=prefix/np.arange(1,n+1);oracle=np.cumsum(np.sort(e))/np.arange(1,n+1)
 curve=np.r_[curve[0],curve];oracle=np.r_[oracle[0],oracle];random=np.full(n+1,e.mean())
 return {'coverage':coverage,'risk':curve,'oracle':oracle,'random':random,
         'AUSE':float(np.trapezoid(curve-oracle,coverage)),'AURG':float(np.trapezoid(random-curve,coverage))}
def corr(x,y):
 if np.ptp(x)==0 or np.ptp(y)==0:return None,None
 return float(spearmanr(x,y).statistic),float(pearsonr(x,y).statistic)
def zero_extended_depth_errors(pred,gt,mask,admission):
 admission.require();p=np.asarray(pred,dtype=float);g=np.asarray(gt,dtype=float);m=np.asarray(mask,dtype=bool)
 if not(p.shape==g.shape==m.shape):raise ValueError('Pixel grids differ')
 valid=m&np.isfinite(g)&(g>0)
 if not valid.any() or not np.isfinite(p[valid]).all() or (p[valid]<0).any():raise ValueError('Invalid zero-extended diagnostic prediction')
 relative=np.abs(p[valid]-g[valid])/(g[valid]+1e-12)
 with np.errstate(divide='ignore'):logarithmic=np.abs(np.log(p[valid])-np.log(g[valid]))
 return relative,logarithmic,valid
def summaries(a):
 a=np.asarray(a);finite=np.isfinite(a);v=a[finite]
 return {'shape':list(a.shape),'finite_count':int(finite.sum()),'nan_count':int(np.isnan(a).sum()),'inf_count':int(np.isinf(a).sum()),
  'min':float(v.min()),'max':float(v.max()),'mean':float(v.mean()),'median':float(np.median(v)),'standard_deviation':float(v.std()),
  **{'P'+str(q):float(np.percentile(v,q)) for q in [1,5,25,75,95,99]},
  'negative_count':int((v<0).sum()),'above_one_count':int((v>1).sum())}
def load_records():
 records=[]
 for folder in [ROOT/'01_smoke/smoke_qualified',ROOT/'02_pilot/pilot']:
  receipt=json.loads((folder/'INFERENCE_RECEIPT.json').read_text());assert receipt['status']=='PASS'
  for row in receipt['results']:
   p=folder/pathlib.PurePosixPath(row['output']).name
   if sha(p)!=row['sha256']:raise RuntimeError('Output hash mismatch')
   row['local_npz']=str(p);records.append(row)
 assert len(records)==16
 return records
def gt_record(row,diagnostic_zero=False):
 item=row['sample'];seq=item['sequence_id'];frame=item['frame_id']
 directory=ROOT.parents[1]/'data/mvs_synth/GTAV_540'/seq if seq=='0000' else ROOT/'inputs/MVS-Synth/GTAV_540'/seq
 depth=directory/'depths'/(frame+'.exr')
 f=OpenEXR.File(str(depth),separate_channels=True);g=f.channels()['Y'].pixels.astype(np.float64)
 with np.load(row['local_npz'],allow_pickle=False) as a:
  pred=a['native_depth'].astype(float);valid=np.isfinite(g)&(g>0)
  if pred.shape!=g.shape or item['input_hw']!=list(g.shape):raise RuntimeError('GT/model grids differ')
  if not np.isfinite(pred[valid]).all() or (pred[valid]<(0 if diagnostic_zero else np.nextafter(0.,1.))).any():raise RuntimeError('Invalid prediction on valid GT')
  c=a['native_confidence'].astype(float)
  signals={'NativeConfidence':-c,'FlipRelative':a['flip_relative_disagreement'].astype(float),
           'InitialBinEntropy':restore_bin(a['native_bin_entropy'],row),'FlipLog':a['flip_log_disagreement'].astype(float)}
  if diagnostic_zero:
   flipped=a['flip_depth'][:,::-1].astype(float)
   if not np.isfinite(flipped[valid]).all() or (flipped[valid]<0).any():raise RuntimeError('Invalid diagnostic flipped depth')
   signals['FlipRelative']=np.abs(pred-flipped)/(np.abs(pred)+1e-6)
   signals['FlipLog']=np.abs(np.log(pred+1e-6)-np.log(flipped+1e-6))
  initial=restore_bin(a['native_initial_depth'],row)*item['fx']/1000.
 rgb=np.asarray(Image.open(directory/'images'/(frame+'.png')).convert('RGB'),dtype=float)/255.
 gray=rgb@np.array([.299,.587,.114]);texture=np.hypot(sobel(gray,0),sobel(gray,1))
 return {'row':row,'gt':g,'prediction':pred,'valid':valid,'raw_confidence':c,'signals':signals,'initial':initial,
         'texture':texture,'gt_path':str(depth),'gt_sha256':sha(depth)}
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 parser=argparse.ArgumentParser();parser.add_argument('--diagnostic-zero-extension',action='store_true');parser.add_argument('--diagnostic-output',default='diagnostic_zero_extension_001');args=parser.parse_args()
 out=ROOT/'04_evaluation'
 if args.diagnostic_zero_extension:
  if args.diagnostic_output not in ['diagnostic_zero_extension_001','diagnostic_zero_extension_002']:raise ValueError('Owned diagnostic output only')
  out=out/args.diagnostic_output;out.mkdir(exist_ok=False)
 start=time.perf_counter();records=load_records()
 stats=[];times=[];outputindex=[]
 for row in records:
  item=row['sample'];outputindex.append({'sample_id':item['sample_id'],'dataset':item['dataset'],'sequence':item['sequence_id'],
       'frame_id':item['frame_id'],'environment':item['environment'],'path':row['local_npz'],'sha256':row['sha256'],'bytes':row['bytes']})
  with np.load(row['local_npz'],allow_pickle=False) as a:
   for field in ['native_confidence','native_canonical_confidence','native_depth','native_depth_unclipped','flip_confidence','flip_relative_disagreement','flip_log_disagreement','native_bin_entropy','native_bin_variance','native_bin_max_probability','native_effective_bins']:
    summary=summaries(a[field]);summary.pop('shape');stats.append({'sample_id':item['sample_id'],'dataset':item['dataset'],'environment':item['environment'],'field':field,**summary})
   if not np.isfinite(a['native_confidence']).all() or not np.isfinite(a['flip_confidence']).all():raise RuntimeError('Nonfinite score')
  for t in row['times']:times.append({'sample_id':item['sample_id'],'dataset':item['dataset'],'environment':item['environment'],**{k:v for k,v in t.items() if k not in ['canonical_shape','bin_shape']}})
 csvwrite(out/'OUTPUT_NUMERICAL_AUDIT.csv',stats);csvwrite(out/'INFERENCE_TIMING_MEMORY.csv',times)
 dump(out/'RAW_OUTPUT_INDEX.json',{'files':outputindex,'unique_samples':16,'GT_data_in_model_inputs':False})
 # Independently recalculate initial-bin statistics from the preserved real logits.
 first=records[0]
 with np.load(first['local_npz'],allow_pickle=False) as a:
  recomputed=depth_bin_statistics(a['native_raw_bin_logits'],a['native_anchors'])
  comparisons=[]
  for mine,saved in [('entropy','bin_entropy'),('variance','bin_variance'),('mean_initial_depth','initial_depth'),('max_probability','bin_max_probability'),('effective_bins','effective_bins')]:
   lhs=recomputed[mine];rhs=a['native_'+saved]
   close=bool(np.allclose(lhs,rhs,rtol=5e-7,atol=1e-5))
   comparisons.append({'field':saved,'max_abs_difference':float(np.max(np.abs(lhs-rhs))),'allclose_float32_storage':close,'rtol':5e-7,'atol':1e-5})
   if not close:raise RuntimeError('Real bin statistics reconstruction mismatch')
 dump(out/'REAL_BIN_RECONSTRUCTION.json',{'real_sample':first['sample']['sample_id'],'comparisons':comparisons,'GPU_inference_repeated':False})

 # This branch is explicitly conditional, after calibration-only numeric units.
 gt=[gt_record(r,args.diagnostic_zero_extension) for r in records if r['sample']['dataset']=='MVS-Synth']
 calibration=[r for r in gt if r['row']['sample']['sequence_id']=='0000']
 test=[r for r in gt if r['row']['sample']['sequence_id']=='0001']
 assert len(calibration)==len(test)==3
 logs=np.concatenate([np.log(r['gt'][r['valid']])-np.log(r['prediction'][r['valid']]) for r in calibration])
 scale=float(np.exp(np.median(logs)))
 native_gt_values=np.concatenate([r['gt'][r['valid']] for r in calibration]);distance=np.quantile(native_gt_values,[1/3,2/3])
 texture_values=np.concatenate([r['texture'][r['valid']] for r in calibration]);texture_thresholds=np.quantile(texture_values,[.25,.75])
 scaleinfo={'scale_prediction_to_native_GT':scale,'formula':'exp(median(log(GT)-log(pred)))','fitted_on_sequences':['0000'],'test_sequences':['0001'],
            'calibration_frames':['0000','0049','0099'],'physical_meter_claim':False,'metric_zero_shot_claim':False,
            'GT_unit':'MVS_NATIVE_UNIT_AFTER_CALIBRATION_ONLY_GLOBAL_SCALE','conditional_accuracy_analysis':True,
            'distance_terciles_native_units':distance.tolist(),'texture_quartiles':texture_thresholds.tolist(),
            'unit_status':'Dataset creator has not established physical conversion in inspected sources',
            'not_a_confidence_or_neural_network_fit':True}
 dump(out/'CALIBRATION_ONLY_DEPTH_SCALE.json',scaleinfo)
 admission=GTAdmission(True,True,True,True,'MVS-Synth distinct sequence IDs','CALIBRATED_MVS_NATIVE_UNIT')
 metricrows=[];curves=[];strata=[];errors=[];bins=[];calibration_data={k:[] for k in ['NativeConfidence','FlipRelative','InitialBinEntropy']}
 for record in gt:
  row=record['row'];item=row['sample'];valid=record['valid'];pred=record['prediction']*scale;g=record['gt']
  if args.diagnostic_zero_extension:
   relerr,logerr,mask=zero_extended_depth_errors(pred,g,valid,admission)
  else:relerr,logerr,mask=depth_errors(pred,g,valid,admission)
  role='CALIBRATION' if item['sequence_id']=='0000' else 'TEST'
  error_map=np.full(g.shape,np.nan);error_map[mask]=relerr
  errors.append({'sample_id':item['sample_id'],'sequence':item['sequence_id'],'role':role,'valid_pixels':int(mask.sum()),
                 'AbsRel_mean':float(relerr.mean()),'AbsLog_mean':float(logerr.mean()) if np.isfinite(logerr).all() else None,
                 'AbsLog_infinite_count':int(np.isinf(logerr).sum()),'AbsLog_status':'FINITE' if np.isfinite(logerr).all() else 'INFINITE_ERRORS_RETAINED',
                 'zero_prediction_count':int((pred[mask]==0).sum()),'median_AbsRel':float(np.median(relerr)),
                 'GT_unit':'CALIBRATED_NATIVE_UNIT','physical_metric_accuracy_certified':False})
  h,w=g.shape;yy,xx=np.indices(g.shape)
  border=(xx<.05*w)|(xx>=.95*w)|(yy<.05*h)|(yy>=.95*h)
  grad=np.hypot(sobel(np.where(np.isfinite(g),g,0),0),sobel(np.where(np.isfinite(g),g,0),1))/(np.where(mask,g,1)+1e-12)
  regions={'near_native_tercile':g<=distance[0],'middle_native_tercile':(g>distance[0])&(g<=distance[1]),'far_native_tercile':g>distance[1],
           'low_RGB_texture':record['texture']<=texture_thresholds[0],'high_RGB_texture':record['texture']>=texture_thresholds[1],
           'image_border_5pct':border,'interior':~border,'GT_depth_boundary_proxy':grad>.05}
  for name,signal in record['signals'].items():
   s=signal[mask]
   if not np.isfinite(s).all():raise RuntimeError('Invalid signal on valid GT')
   rho,pearson=corr(relerr,s);rc=fast_rc(relerr,s)
   line={'sample_id':item['sample_id'],'sequence':item['sequence_id'],'role':role,'signal':name,'pixels':len(s),
         'Spearman_error_vs_risk':rho,'Pearson_error_vs_risk':pearson,'AUSE_raw_AbsRel':rc['AUSE'],'AURG_raw_AbsRel':rc['AURG'],
         'conditional_scale_calibrated':True,'secondary_zero_extended_diagnostic':args.diagnostic_zero_extension}
   for threshold in [.1,.2,.5]:
    score=binary_ranking(relerr>threshold,s)
    line['AUROC_gt_'+str(threshold)]=score['AUROC'];line['AUPRC_AP_gt_'+str(threshold)]=score['AUPRC']
    line['prevalence_gt_'+str(threshold)]=float((relerr>threshold).mean())
   if name=='NativeConfidence':line['Spearman_error_vs_raw_confidence']=None if rho is None else -rho
   if name=='InitialBinEntropy':
    initial_error=np.abs(record['initial'][mask]*scale-g[mask])/g[mask]
    line['Spearman_initial_error_vs_entropy']=corr(initial_error,s)[0]
   metricrows.append(line)
   if role=='TEST':
    indices=np.unique(np.r_[0,np.linspace(1,len(s),201).astype(int)])
    for i in indices:curves.append({'sample_id':item['sample_id'],'signal':name,'coverage':float(rc['coverage'][i]),'risk':float(rc['risk'][i]),'oracle':float(rc['oracle'][i]),'random':float(rc['random'][i])})
    for b in reliability_bins(relerr,record['raw_confidence'][mask] if name=='NativeConfidence' else s):bins.append({'sample_id':item['sample_id'],'signal':name,**b})
    for region,region_mask in regions.items():
     keep=region_mask[mask]
     if keep.sum()<30:continue
     bs=binary_ranking(relerr[keep]>.2,s[keep])
     strata.append({'sample_id':item['sample_id'],'signal':name,'stratum':region,'pixels':int(keep.sum()),
                    'AbsRel_mean':float(relerr[keep].mean()),'Spearman_error_vs_risk':corr(relerr[keep],s[keep])[0],'AUROC_error_gt_0_2':bs['AUROC']})
   if role=='CALIBRATION' and name in calibration_data:
    sample_mask=mask.copy();sample_mask[:]=False;sample_mask[::8,::8]=mask[::8,::8]
    calibration_data[name].append((signal[sample_mask],error_map[sample_mask]>.2))
  dump(out/(item['sample_id']+'_GT_PAIRING.json'),{'GT_path':record['gt_path'],'GT_sha256':record['gt_sha256'],'input_RGB_sha256':item['rgb_sha256'],
        'input_hw':item['input_hw'],'GT_hw':list(g.shape),'role':role,'physical_units_certified':False,'scale_applied':scale})
 csvwrite(out/'CONDITIONAL_NATIVE_UNIT_METRICS.csv',metricrows);csvwrite(out/'CONDITIONAL_DEPTH_ERRORS.csv',errors)
 csvwrite(out/'RISK_COVERAGE_SOURCE_DATA.csv',curves);csvwrite(out/'CONDITIONAL_TEST_STRATA.csv',strata);csvwrite(out/'SCORE_ERROR_BINS.csv',bins)

 # A calibration mapping for one explicitly defined event, never raw confidence ECE.
 probabilityrows=[];probabilitymodels=[]
 for name,chunks in calibration_data.items():
  x=np.concatenate([z[0] for z in chunks]);y=np.concatenate([z[1] for z in chunks]).astype(float)
  mean=float(x.mean());sd=float(x.std());z=(x-mean)/(sd if sd>0 else 1.)
  if not 0<y.mean()<1:continue
  initial=[0.,float(np.log(y.mean()/(1-y.mean())))]
  def objective(theta):
   v=theta[0]*z+theta[1];pr=expit(v)
   return float(np.mean(np.logaddexp(0,v)-y*v)),np.array([np.mean((pr-y)*z),np.mean(pr-y)])
  fit=minimize(objective,initial,jac=True,bounds=[(0,None),(None,None)],method='L-BFGS-B',options={'maxiter':200,'ftol':1e-12})
  if not fit.success:raise RuntimeError('Probability calibration failed')
  model={'signal':name,'standardize_mean':mean,'standardize_SD':sd,'nonnegative_risk_coefficient':float(fit.x[0]),'intercept':float(fit.x[1]),
         'event':'AbsRel>0.2 after calibration-only global scale','fitted_on_sequences':['0000'],'grid_stride':8,'calibration_pixels':len(x),
         'test_fitted':False,'network_training':False}
  probabilitymodels.append(model)
  for record in test:
   keep=record['valid'];risk=record['signals'][name][keep];err=np.abs(record['prediction'][keep]*scale-record['gt'][keep])/record['gt'][keep]
   prob=expit(fit.x[0]*(risk-mean)/(sd if sd>0 else 1.)+fit.x[1])
   result=probability_calibration(prob,err>.2,fitted_on_sequences=['0000'],test_sequences=['0001'],event_definition=model['event'])
   probabilityrows.append({'sample_id':record['row']['sample']['sample_id'],'signal':name,'probability_event':model['event'],'ECE_10_equal_width_bins':result['ECE'],
                          'Brier_mean':float(np.mean((prob-(err>.2))**2)),'is_native_raw_probability':False,'conditional_scale_calibrated':True})
 dump(out/'CALIBRATION_ONLY_PROBABILITY_MODELS.json',{'models':probabilitymodels,'test_sequence_used_for_fit':False})
 csvwrite(out/'CONDITIONAL_CALIBRATED_EVENT_ECE.csv',probabilityrows)
 testrows=[r for r in metricrows if r['role']=='TEST'];aggregate=[]
 for name in record['signals']:
  own=[r for r in testrows if r['signal']==name]
  keys=[k for k in own[0] if k.startswith(('Spearman','Pearson','AUROC','AUPRC','AUSE','AURG'))]
  aggregate.append({'signal':name,'test_sequence_count':1,'test_frame_count':3,'aggregation':'Equal-frame macro within one held-out sequence',
   **{k:float(np.mean([r[k] for r in own if r.get(k) is not None])) for k in keys},'cross_sequence_CI':None,
   'evidence_scope':'SECONDARY_ZERO_EXTENDED_CALIBRATED_NATIVE_UNITS_NOT_STRICT_OR_METRIC_PASS'})
 csvwrite(out/'CONDITIONAL_TEST_MACRO.csv',aggregate)
 dump(out/'EVALUATION_STATUS.json',{'inference_samples':16,'GPU_model_forwards':33,'CPU_tests':61,'conditional_GT_frames':6,
   'calibration_sequence':'0000','test_sequence':'0001','conditional_native_unit_evaluation':'COMPLETE',
   'physical_metric_accuracy':'BLOCKED_UNKNOWN_RAW_GT_UNIT','sequence_generalization_certified':False,'VIPER_accuracy_certified':False,
   'strict_GT_gate':'FAILED_BEFORE_CALIBRATION','zero_extended_secondary_diagnostic':args.diagnostic_zero_extension,
   'producer_script_sha256':sha(pathlib.Path(__file__)),'preregistration_sha256':sha(ROOT/'experiments/configs/EVALUATION_PREREGISTRATION.json'),
   'diagnostic_amendment_sha256':sha(ROOT/'experiments/configs/DIAGNOSTIC_ZERO_EXTENSION_AMENDMENT.json'),
   'integration_decision':'NO-GO_INSUFFICIENT_VIPER_AND_CROSS_SEQUENCE_EVIDENCE','elapsed_CPU_seconds':time.perf_counter()-start})
 print(json.dumps({'status':'CONDITIONAL_NATIVE_UNIT_ANALYSIS_COMPLETE','scale':scale,'test_macro':aggregate},indent=2))

if __name__=='__main__':main()
