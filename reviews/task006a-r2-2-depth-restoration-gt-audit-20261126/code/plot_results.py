"""Scientific plots from actual sealed and restored outputs, no simulated results."""
import csv
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from common import *

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
    'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,
    'svg.fonttype':'none','pdf.fonttype':42,'legend.frameon':False})
COLORS={'old':'#67798d','new':'#c38346','first':'#578a90','second':'#9c79a3'}
def table(name):
    with (ROOT/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def save(fig,name):
    for ext in ['png','svg','pdf']:fig.savefig(ROOT/'figures'/(name+'.'+ext),dpi=220,bbox_inches='tight')
    plt.close(fig)

def spatial():
    data=table('04_evaluation/PAIRED_DEPTH_ERROR_METRICS.csv')
    scales=json.loads((ROOT/'04_evaluation/CALIBRATION_ONLY_SCALES.json').read_text())['per_variant_native_unit_scale']
    fig,ax=plt.subplots(3,5,figsize=(13,7),layout='constrained')
    for i,frame in enumerate(['0000','0049','0099']):
        sid='MVS_0001_'+frame;g=depth(gt_dir('0001')/'depths'/(frame+'.exr'));valid=np.isfinite(g)&(g>0)
        rgb=np.asarray(Image.open(gt_dir('0001')/'images'/(frame+'.png')).convert('RGB'))
        with np.load(ROOT/'04_evaluation/pixel_maps'/(sid+'.npz'),allow_pickle=False) as a:
            values=[rgb,np.ma.masked_where(~valid,g),np.ma.masked_where(~valid,a['v1_prediction_scaled_native']),
                np.ma.masked_where(~valid,a['v1_AbsRel']),a['confidence_raw']]
            for j,v in enumerate(values):
                kwargs={} if j==0 else ({'cmap':'viridis','norm':LogNorm(70,2000)} if j in [1,2] else
                  {'cmap':'magma','vmin':0,'vmax':1} if j==3 else {'cmap':'viridis','vmin':.85,'vmax':1.0})
                im=ax[i,j].imshow(v,**kwargs);ax[i,j].set_xticks([]);ax[i,j].set_yticks([])
                if j==0:ax[i,j].set_ylabel('0001 / '+frame,fontweight='bold')
                if i==0:ax[i,j].set_title(['RGB, unchanged','GT, native units','Bilinear depth, scaled','AbsRel (display 0–1)','Raw confidence (0.85–1)'][j],fontsize=9)
                if i==2 and j:fig.colorbar(im,ax=ax[:,j],orientation='horizontal',shrink=.85,pad=.015)
    fig.suptitle('Same RGB and GT grids · sequence0001 is previously observed audit data\nOne Calibration0000 scale; no physical-meter or new-test claim',fontsize=12)
    save(fig,'MVS_SPATIAL_ERROR_CONFIDENCE')

def zeros():
    frame='0099';sid='MVS_0001_'+frame
    r=next(r for r in records() if r['sample']['sample_id']==sid)
    rgb=np.asarray(Image.open(gt_dir('0001')/'images'/(frame+'.png')).convert('RGB'))
    zero=table('04_evaluation/ORIGINAL_SEVEN_ZERO_PIXELS.csv')
    x=np.array([int(z['x']) for z in zero]);y=np.array([int(z['y']) for z in zero])
    with np.load(r['local_npz'],allow_pickle=False) as a,np.load(ROOT/'02_restoration/torch_CPU'/(sid+'.npz'),allow_pickle=False) as b:
        old=a['native_depth'];new=b['native_bilinear_same_focal']
    with np.load(ROOT/'04_evaluation/pixel_maps'/(sid+'.npz'),allow_pickle=False) as a:e=a['v1_AbsRel']
    fig,ax=plt.subplots(2,3,figsize=(11,6.2),layout='constrained')
    ax[0,0].imshow(rgb);ax[0,0].scatter(x,y,s=24,facecolors='none',edgecolors='#ffb04c');ax[0,0].set_title('All 7 original zero predictions')
    ax[0,1].imshow(old,cmap='viridis',vmin=0,vmax=25);ax[0,1].set_title('Frozen bicubic + clamp')
    ax[0,2].imshow(new,cmap='viridis',vmin=0,vmax=25);ax[0,2].set_title('Bilinear, identical focal factor')
    crop=np.s_[145:207,638:724]
    ax[1,0].imshow(rgb[crop]);ax[1,0].set_title('Documented crop: x638–723, y145–206')
    ax[1,1].imshow(new[crop],cmap='viridis',vmin=0,vmax=25);ax[1,1].set_title('Positive values; display depth 0–25')
    im=ax[1,2].imshow(e[crop],cmap='magma',vmin=0,vmax=1);ax[1,2].set_title('Residual AbsRel after restoration')
    fig.colorbar(im,ax=ax[1,2],orientation='horizontal',shrink=.8,pad=.02)
    for a in ax.flat:a.set_xticks([]);a.set_yticks([])
    fig.suptitle('Interpolation artifacts are removed; remaining depth error is evaluated separately',fontsize=12)
    save(fig,'ZERO_PIXEL_RESTORATION_DETAIL')

def paired():
    data=table('04_evaluation/PAIRED_DEPTH_ERROR_METRICS.csv');fig,ax=plt.subplots(1,2,figsize=(9,3.7),layout='constrained')
    for i,f in enumerate(['0000','0049','0099']):
        sid='MVS_0001_'+f;old=next(r for r in data if r['sample_id']==sid and r['variant']=='R2_1_BICUBIC_FROZEN')
        new=next(r for r in data if r['sample_id']==sid and r['variant']=='BILINEAR_SAME_FOCAL')
        for j,key in enumerate(['AbsRel_mean','severe_error_ge_1_fraction']):
            scale=1 if j==0 else 100;v=[float(old[key])*scale,float(new[key])*scale]
            ax[j].plot([0,1],v,'o-',label=f,linewidth=1.6,markersize=5)
            ax[j].annotate(f,(1,v[1]),xytext=(5,0),textcoords='offset points',fontsize=8)
    ax[0].set_ylabel('Mean absolute relative error');ax[1].set_ylabel('Severe error ≥100% (% of valid GT)')
    for a in ax:a.set_xticks([0,1],['Frozen bicubic','Bilinear']);a.set_xlim(-.15,1.45);a.grid(axis='y',alpha=.2)
    ax[0].set_title('a  Numerical repair is not an accuracy gain',loc='left');ax[1].set_title('b  Report all severe errors',loc='left')
    fig.suptitle('Three frames of previously observed sequence0001 · identical GT masks · separate Calibration0000 scales',fontsize=10)
    save(fig,'PAIRED_ERROR_AND_SEVERE')

def confidence():
    rows=table('04_evaluation/CONFIDENCE_ERROR_BINS.csv');fig,ax=plt.subplots(2,3,figsize=(11,5.8),layout='constrained')
    for i,f in enumerate(['0000','0049','0099']):
        sid='MVS_0001_'+f;own=[r for r in rows if r['sample_id']==sid and r['variant']=='BILINEAR_SAME_FOCAL']
        x=[int(r['confidence_bin_from_calibration'])+1 for r in own]
        for j,key in enumerate(['AbsRel_mean','severe_fraction']):
            y=[float(r[key])*(100 if j else 1) for r in own];ax[j,i].plot(x,y,'o-',color=COLORS['new'],markersize=4)
            ax[j,i].grid(axis='y',alpha=.2);ax[j,i].set_xticks([1,5,10]);ax[j,i].set_xlim(.5,10.5)
            if i==0:ax[j,i].set_ylabel('Mean AbsRel' if j==0 else 'Severe error fraction (%)')
            if j==0:ax[j,i].set_title('0001 / '+f)
            else:ax[j,i].set_xlabel('Calibration0000 raw-confidence bin')
    fig.suptitle('Raw confidence is a score, not P(correct) · bin boundaries fixed from0000\nSeverity event: AbsRel ≥1.0; no probability fitting in R2.2',fontsize=11)
    save(fig,'CONFIDENCE_ERROR_DIAGNOSTICS')

def geometry():
    rows=table('03_gt_audit/ALL_198_ADJACENT_Z_DEPTH_PAIRS.csv');ct=table('03_gt_audit/MAX_TRANSLATION_ALIGNMENT_CONTROLS.csv')
    fig,ax=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    for seq,color in [('0000',COLORS['first']),('0001',COLORS['second'])]:
        own=[r for r in rows if r['sequence']==seq];y=[max(float(r['median_relative_depth_disagreement'])*100,1e-12) for r in own]
        ax[0].plot(range(99),y,label=seq,color=color,alpha=.85,linewidth=1)
        controls=[r for r in ct if r['sequence']==seq and r['GT_multiplier_only_not_translation']=='1.0']
        yy=[float(next(r for r in controls if r['depth_hypothesis']==kind)['median_relative_depth_disagreement'])*100 for kind in ['z','range']]
        ax[1].plot([0,1],yy,'o-',label=seq,color=color)
        own=[r for r in ct if r['sequence']==seq and r['depth_hypothesis']=='z']
        own=sorted(own,key=lambda r:float(r['GT_multiplier_only_not_translation']))
        ax[2].plot([float(r['GT_multiplier_only_not_translation']) for r in own],[float(r['median_relative_depth_disagreement'])*100 for r in own],'o-',label=seq,color=color)
    ax[0].set_yscale('log');ax[0].set_xlabel('Adjacent frame pair');ax[0].set_ylabel('Pair-median depth disagreement (%)');ax[0].set_title('a  198 adjacent Z-depth checks',loc='left')
    ax[1].set_xticks([0,1],['Z depth','Ray range']);ax[1].set_ylabel('Depth disagreement (%)');ax[1].set_title('b  Largest-translation pairs',loc='left')
    ax[2].set_xscale('log');ax[2].set_yscale('log');ax[2].set_xlabel('GT multiplier (pose translation fixed)');ax[2].set_ylabel('Depth disagreement (%)');ax[2].set_title('c  Internal scale consistency only',loc='left')
    for a in ax:a.grid(alpha=.2);a.legend(fontsize=7)
    fig.suptitle('Geometry supports matching native units; jointly scaling depth and translation still cannot identify meters',fontsize=11)
    save(fig,'GEOMETRY_ALIGNMENT_UNIT_AMBIGUITY')

def main():
    cpu_only()
    for f in [spatial,zeros,paired,confidence,geometry]:f();print('FIGURE',f.__name__,flush=True)
    with (ROOT/'figures/FIGURE_CAPTIONS.md').open('x',encoding='utf-8') as f:
        f.write('''# R2.2 figure captions and integrity notes

All plots use actual archived inference or current CPU-audit results. No new model inference.
Sequence0001 was observed in R2.1. Three frames are technical samples, not three independent sequences. No CI, significance or meter claim.

1. **MVS_SPATIAL_ERROR_CONFIDENCE**: rows0001/0000,0049,0099. Native RGB unchanged; GT and prediction display70–2000 native units on a log scale, invalid GT gray. Prediction uses bilinear with the legacy focal factor and one Calibration0000 scale. AbsRel colorbar is display-limited0–1; confidence0.85–1 is a raw-score display range, not a probability. Original arrays and statistics are never display-clipped. Source:pixel_maps, PAIRED_DEPTH_ERROR_METRICS.csv, original RGB/GT SHA index.
2. **ZERO_PIXEL_RESTORATION_DETAIL**: all seven historical zero coordinates are overlaid on the full RGB. Lower row is an explicitly labeled crop x638:724,y145:207. Depth display0–25 uses the same scale in both compared images. Repaired pixels can retain prediction error. Source:ORIGINAL_SEVEN_ZERO_PIXELS.csv and raw/restored arrays.
3. **PAIRED_ERROR_AND_SEVERE**: paired per-frame mean AbsRel and percent with error≥1.0 for three already-observed frames. Same finite-positive GT masks, per-variant calibration-only global scale. Lines connect the same image, not independent replicate experiments. Source:PAIRED_DEPTH_ERROR_METRICS.csv.
4. **CONFIDENCE_ERROR_DIAGNOSTICS**: mean error and severe-error frequency in bins with boundaries derived only from Calibration0000. Bin1 is lowest raw confidence, bin10 highest. This is a descriptive score-error plot, not a calibration reliability diagram. Source:CONFIDENCE_ERROR_BINS.csv.
5. **GEOMETRY_ALIGNMENT_UNIT_AMBIGUITY**:198 adjacent-pair medians and pose-only largest-translation controls. Panelc rescales only GT depth, keeping native translations fixed; it checks consistency of those numbers. Scaling depth and translation together leaves projection invariant, so no panel establishes meters. Source:ALL_198_ADJACENT_Z_DEPTH_PAIRS.csv and MAX_TRANSLATION_ALIGNMENT_CONTROLS.csv.

Exports:Python matplotlib only, PNG220dpi, editable-label SVG, embedded-raster PDF. Pseudocolor and crops are documented above. RGB/GT input files are excluded from public package; derived figures and prediction/error arrays are included.
''')
if __name__=='__main__':main()
