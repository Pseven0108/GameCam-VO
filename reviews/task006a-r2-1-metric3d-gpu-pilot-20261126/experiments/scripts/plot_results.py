"""Python-only actual-output figures. No synthetic image or accuracy substitutions."""
import csv,json,os,pathlib
import numpy as np
from PIL import Image
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from evaluate_pilot import ROOT,load_records,gt_record
OUT=ROOT/'figures';EVAL=ROOT/'04_evaluation/diagnostic_zero_extension_002'
COLORS={'NativeConfidence':'#4677A4','FlipRelative':'#C58C57','InitialBinEntropy':'#74A28D'}
def save(fig,name):
 fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 contract={'backend':'Python matplotlib only','archetype':'image plate + quantitative comparison',
  'conclusions':['Real raw confidence is unbounded, not a probability','Five VIPER environments have real model outputs, no VIPER depth GT',
                 'One-sequence held-out, scale-calibrated diagnostic is distinct from physical metric accuracy',
                 'Entropy direction is not repaired using test results'],
  'display_only_clipping':'GT/error and TTA color limits labelled; original arrays are unchanged',
  'source_data':'Raw NPZ files and CSVs preserved with SHA','export':['PNG220dpi','editable SVG'],
  'no_independent_pixel_error_bars':True,'no_GT_for_VIPER_accuracy_claims':True}
 with (OUT/'FIGURE_CONTRACT.json').open('x',encoding='utf-8') as f:f.write(json.dumps(contract,indent=2)+'\n')
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
 records=load_records();image_map={r['sample_id']:r['path'] for r in json.loads((ROOT/'evidence/FIGURE_INPUT_IDENTITY.json').read_text())['files']}
 vip=[r for r in records if r['sample']['dataset']=='VIPER'];envs=['Day','Sunset','Rain','Night','Snow']
 selected=[next(r for r in vip if r['sample']['environment']==env) for env in envs]
 cs=[]
 for r in vip:
  with np.load(r['local_npz'],allow_pickle=False) as a:cs.append(a['native_confidence'].reshape(-1))
 vmin=min(float(x.min()) for x in cs);vmax=max(float(x.max()) for x in cs)
 fig,axes=plt.subplots(5,5,figsize=(16.5,10.4),layout='constrained')
 titles=['RGB','Depth (baseline output units)','Native confidence (raw)','Flip relative disagreement','Initial entropy / log(256)']
 images=[]
 for i,r in enumerate(selected):
  sample=r['sample'];a=np.load(r['local_npz'],allow_pickle=False);rgb=np.asarray(Image.open(image_map[sample['sample_id']]).convert('RGB'))
  values=[rgb,a['native_depth'],a['native_confidence'],a['flip_relative_disagreement'],a['native_bin_entropy']/np.log(256)]
  for j,value in enumerate(values):
   ax=axes[i,j]
   if j==0:im=ax.imshow(value)
   elif j==1:im=ax.imshow(value,cmap='magma',norm=LogNorm(vmin=.5,vmax=100))
   elif j==2:im=ax.imshow(value,cmap='viridis',vmin=vmin,vmax=vmax)
   elif j==3:im=ax.imshow(value,cmap='inferno',vmin=0,vmax=1)
   else:im=ax.imshow(value,cmap='cividis',vmin=0,vmax=1)
   ax.set_xticks([]);ax.set_yticks([])
   if i==0:ax.set_title(titles[j],fontsize=9)
   if j==0:ax.set_ylabel(sample['environment']+'\n'+sample['sequence_id']+'/'+sample['frame_id'],fontsize=9)
   if i==4 and j>0:fig.colorbar(im,ax=ax,orientation='horizontal',fraction=.065,pad=.04)
  a.close()
 fig.suptitle('Real Metric3D outputs on VIPER: 5 environments; no VIPER depth-GT accuracy claim',fontsize=14)
 save(fig,'VIPER_FIVE_ENVIRONMENT_REAL_OUTPUTS')

 fig,ax=plt.subplots(figsize=(8.4,4.2),layout='constrained')
 bins=np.linspace(vmin,vmax,75);palette=['#4677A4','#C58C57','#74A28D','#8C729F','#7B858F']
 for env,color in zip(envs,palette):
  vals=[]
  for r in vip:
   if r['sample']['environment']==env:
    with np.load(r['local_npz'],allow_pickle=False) as a:vals.append(a['native_confidence'].reshape(-1))
  ax.hist(np.concatenate(vals),bins=bins,density=True,histtype='step',linewidth=1.5,color=color,label=env+' (2 images)')
 ax.axvline(0,color='gray',linestyle=':',linewidth=.8);ax.axvline(1,color='gray',linestyle=':',linewidth=.8)
 ax.set_xlabel('Native raw confidence (no sigmoid or clipping)');ax.set_ylabel('Pixel histogram density');ax.legend(fontsize=8)
 ax.set_title('Descriptive distributions only; pixels are not independent scene replicates')
 save(fig,'RAW_CONFIDENCE_ENVIRONMENT_DISTRIBUTIONS')

 test=[r for r in records if r['sample']['dataset']=='MVS-Synth' and r['sample']['sequence_id']=='0001']
 scale=json.loads((EVAL/'CALIBRATION_ONLY_DEPTH_SCALE.json').read_text())['scale_prediction_to_native_GT']
 fig,axes=plt.subplots(3,5,figsize=(16,7.8),layout='constrained')
 for i,r in enumerate(test):
  data=gt_record(r,diagnostic_zero=True);g=data['gt'];mask=data['valid'];pred=data['prediction']*scale
  error=np.full(g.shape,np.nan);error[mask]=np.abs(pred[mask]-g[mask])/g[mask]
  rgb=np.asarray(Image.open(image_map[r['sample']['sample_id']]).convert('RGB'))
  values=[rgb,np.where(mask,g,np.nan),np.where(mask,pred,np.nan),error,data['raw_confidence']]
  for j,value in enumerate(values):
   ax=axes[i,j]
   if j==0:im=ax.imshow(value)
   elif j in [1,2]:im=ax.imshow(value,cmap='magma',norm=LogNorm(vmin=30,vmax=5000))
   elif j==3:im=ax.imshow(value,cmap='inferno',vmin=0,vmax=1)
   else:im=ax.imshow(value,cmap='viridis',vmin=vmin,vmax=vmax)
   ax.set_xticks([]);ax.set_yticks([])
   if i==0:ax.set_title(['RGB','GT (native units)','Prediction x frozen scale','AbsRel (display clipped at 1)','Native confidence'][j],fontsize=9)
   if j==0:ax.set_ylabel('Test0001 / '+r['sample']['frame_id'])
   if i==2 and j>0:fig.colorbar(im,ax=ax,orientation='horizontal',fraction=.065,pad=.04)
 fig.suptitle('Secondary diagnostic: scale fitted only on sequence0000; no physical-meter or strict-GT PASS',fontsize=13)
 save(fig,'MVS_HELDOUT_NATIVE_UNIT_DIAGNOSTIC')

 metrics=list(csv.DictReader((EVAL/'CONDITIONAL_NATIVE_UNIT_METRICS.csv').open()))
 curves=list(csv.DictReader((EVAL/'RISK_COVERAGE_SOURCE_DATA.csv').open()))
 fig,axes=plt.subplots(1,3,figsize=(12.8,3.8),layout='constrained')
 signals=list(COLORS)
 for k,threshold in enumerate(['0.1','0.2','0.5']):
  ax=axes[k]
  for i,name in enumerate(signals):
   rows=[r for r in metrics if r['role']=='TEST' and r['signal']==name]
   y=np.array([float(r['AUROC_gt_'+threshold]) for r in rows])
   ax.scatter(i+np.linspace(-.08,.08,len(y)),y,color=COLORS[name],s=25,alpha=.8)
   ax.plot([i-.16,i+.16],[y.mean(),y.mean()],color=COLORS[name],linewidth=2.5)
  ax.axhline(.5,color='gray',linestyle='--',linewidth=.8);ax.set_ylim(0,1)
  ax.set_xticks(range(3),['Native','Flip','Initial entropy'],rotation=15);ax.set_ylabel('AUROC');ax.set_title('AbsRel > '+threshold)
 fig.suptitle('One held-out sequence, 3 frame scores; dots are frames, bars are macro means; no cross-sequence CI',fontsize=10)
 save(fig,'CONDITIONAL_TEST_AUROC_PAIRED_FRAMES')

 fig,ax=plt.subplots(figsize=(7.4,4.2),layout='constrained')
 for name in signals:
  own=[r for r in curves if r['signal']==name];ids=sorted({r['sample_id'] for r in own});ys=[];xs=None
  for sid in ids:
   values=[r for r in own if r['sample_id']==sid];xs=np.array([float(v['coverage']) for v in values]);ys.append([float(v['risk']) for v in values])
  ax.plot(xs,np.mean(ys,axis=0),label=name,color=COLORS[name],linewidth=1.8)
 own=[r for r in curves if r['signal']=='NativeConfidence'];ids=sorted({r['sample_id'] for r in own})
 for field,color in [('random','#888888'),('oracle','#333333')]:
  ys=[[float(r[field]) for r in own if r['sample_id']==sid] for sid in ids]
  ax.plot(xs,np.mean(ys,axis=0),linestyle='--',color=color,label=field)
 ax.set_xlabel('Retained coverage');ax.set_ylabel('Mean AbsRel, raw (not normalized)');ax.legend(fontsize=8)
 ax.set_title('Secondary scale-calibrated diagnostic; all valid GT retained, including zero predictions')
 save(fig,'CONDITIONAL_RISK_COVERAGE')

 captions='''# Figure reading notes

All panels use actual saved outputs. VIPER has no admitted local dense-depth GT;
its heatmaps/histograms are descriptive only. Raw confidence is never sigmoid-normalized.
The five-environment plate shows the first preselected sample in each environment;
both selected frames per environment remain in raw outputs and numerical CSV.

MVS panels use the independently held-out sequence0001, with one global prediction
scale fitted on sequence0000 only. Native units are not certified meters. The strict
GT gate failed at seven zero predictions and remains FAILED. Secondary diagnostics
retain zero predictions as AbsRel=1 and infinite log error; no such pixels are removed.
TTA values for those points are separately recalculated from the user-defined epsilon
formula without rewriting the original saved NaNs. Display limits are only color limits:
depth0.5..100 baseline units, native-GT30..5000, TTA0..1, AbsRel0..1; arrays retain full values.

AUROC dots are three frames from ONE test sequence, not independent sequence replicates.
No statistical significance or cross-sequence confidence interval is claimed. Entropy
keeps its preregistered higher-is-risk direction even when AUROC is below random.
Source data are in 04_evaluation/diagnostic_zero_extension_002 and original NPZ files.
'''
 (OUT/'FIGURE_CAPTIONS.md').write_text(captions,encoding='utf-8')
 print(json.dumps({'figures':5,'formats':['PNG','SVG'],'actual_model_outputs':True,'fake_GT_prediction_panels':False}))
if __name__=='__main__':main()
