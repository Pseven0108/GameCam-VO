"""CPU-only scientific figures from the completed, fixed experiment tables."""
from common import *
from fusion_math import CORE
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize,LogNorm
from PIL import Image

COLORS={'NativeOnly':'#597994','FlipOnly':'#55948B','RankFusion':'#8B6B9D','MaxFusion':'#C48B55'}
LABELS={'NativeOnly':'Native','FlipOnly':'Flip','RankFusion':'Equal rank','MaxFusion':'Max risk'}
VIEW='FROZEN_BICUBIC_ZERO_EXTENDED'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42,'axes.linewidth':.8,'legend.frameon':False})

def main():
    out=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path']);dest=TASK/'figures';dest.mkdir(exist_ok=True)
    def save(fig,name,vector=True):
        fig.savefig(dest/(name+'.png'),dpi=220,bbox_inches='tight',facecolor='white')
        if vector:
            fig.savefig(dest/(name+'.svg'),bbox_inches='tight');fig.savefig(dest/(name+'.pdf'),bbox_inches='tight')
        plt.close(fig)
    table=csvread(out/'metrics_summary.csv');frame=csvread(out/'metrics_per_frame.csv')
    summary={r['method']:r for r in table if r['view']==VIEW}
    fig,axes=plt.subplots(1,4,figsize=(12.2,3.6),layout='constrained')
    for ax,key,better in zip(axes,['AUROC','AP','AUSE','Spearman'],['higher','higher','lower','higher']):
        for i,method in enumerate(CORE):
            r=summary[method];own=[float(t[key]) for t in frame if t['view']==VIEW and t['role']=='PREVIOUSLY_OBSERVED_EVALUATION' and t['method']==method]
            ax.errorbar(i,float(r[key]),yerr=float(r[key+'_SD_across_frames']),fmt='s',color=COLORS[method],capsize=4,markersize=6)
            ax.scatter(i+np.array([-.09,0,.09]),own,color=COLORS[method],s=19,zorder=3)
        ax.set_xticks(range(4),[LABELS[m] for m in CORE],rotation=30,ha='right');ax.set_title(key+' ('+better+' better)');ax.grid(axis='y',alpha=.16)
        if key in ['AUROC','AP']:ax.set_ylim(0,1)
        else:ax.axhline(0,color='.7',lw=.7)
    fig.suptitle('Frozen-cache comparison: three reused frames, one MVS sequence\nSquares = frame macro mean; bars = frame SD, not generalization CI',fontsize=11)
    save(fig,'ranking_metrics')
    fig,axes=plt.subplots(1,2,figsize=(10.5,4),layout='constrained');coverage=csvread(out/'risk_coverage.csv');bins=csvread(out/'risk_error_bins.csv');xx=np.linspace(.01,1,150)
    for method in CORE:
        curves=[]
        for sid in ['MVS_0001_0000','MVS_0001_0049','MVS_0001_0099']:
            own=[r for r in coverage if r['view']==VIEW and r['method']==method and r['sample_id']==sid]
            curves.append(np.interp(xx,[float(r['coverage']) for r in own],[float(r['risk']) for r in own]))
        axes[0].plot(xx,np.mean(curves,axis=0),color=COLORS[method],label=LABELS[method])
        own=[r for r in bins if r['view']==VIEW and r['method']==method]
        yy=[]
        for j in range(10):
            values=[float(r['mean_AbsRel']) for r in own if int(r['risk_percentile_bin'])==j];yy.append(np.mean(values) if values else np.nan)
        axes[1].plot(np.arange(10)+.5,yy,'o-',color=COLORS[method],label=LABELS[method],ms=4)
    oracle=[]
    for sid in ['MVS_0001_0000','MVS_0001_0049','MVS_0001_0099']:
        own=[r for r in coverage if r['view']==VIEW and r['method']=='NativeOnly' and r['sample_id']==sid]
        oracle.append(np.interp(xx,[float(r['coverage']) for r in own],[float(r['oracle']) for r in own]))
    axes[0].plot(xx,np.mean(oracle,axis=0),'--',color='.3',label='Error oracle');axes[0].set(xlabel='Retained coverage',ylabel='Mean AbsRel',title='Risk–coverage, equal-image macro');axes[0].legend(fontsize=8)
    axes[1].set(xlabel='Increasing risk-percentile decile',ylabel='Mean actual AbsRel',title='Continuous error versus risk');axes[1].legend(fontsize=8)
    save(fig,'risk_coverage_and_error_bins')
    fig,axes=plt.subplots(1,4,figsize=(12.2,3.2),layout='constrained')
    weights=[0,.25,.5,.75,1];names=['FlipOnly','RankW25','RankFusion','RankW75','NativeOnly']
    for ax,key in zip(axes,['AUROC','AP','AUSE','Spearman']):
        ax.plot(weights,[float(summary[n][key]) for n in names],'o-',color=COLORS['RankFusion']);ax.axvline(.5,color='.65',ls='--',lw=1);ax.set(xlabel='Fixed Native rank weight',ylabel=key,xticks=weights);ax.grid(alpha=.15)
    fig.suptitle('Sensitivity only: no evaluation-set weight selection',fontsize=11);save(fig,'fixed_weight_sensitivity')
    calibration=csvread(out/'calibration_macro.csv');fig,axes=plt.subplots(1,3,figsize=(10.7,3.5),layout='constrained')
    names=CORE+['CalibrationPrevalence']
    for ax,key in zip(axes,['Brier','NLL','ECE10']):
        own={r['method']:r for r in calibration if r['view']==VIEW and r['analysis']=='probability_metrics'}
        vals=[float(own[n][key]) for n in names];ax.bar(range(5),vals,color=[COLORS.get(n,'#A8ACB0') for n in names],width=.7);ax.set_xticks(range(5),[LABELS.get(n,'Constant') for n in names],rotation=35,ha='right');ax.set_ylabel(key);ax.set_ylim(0,max(vals)*1.22);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Calibration0000 fits → previously observed0001 evaluation; lower is better',fontsize=10);save(fig,'probability_scores')
    fig,axes=plt.subplots(1,2,figsize=(10.2,3.7),layout='constrained')
    regression={r['method']:r for r in calibration if r['view']==VIEW and r['analysis']=='regression_metrics'}
    names=CORE+['CalibrationMeanAbsRel','CalibrationMedianAbsRel']
    for ax,key,title in zip(axes,['AbsRel_prediction_MAE','AbsRel_prediction_RMSE'],['AbsRel amplitude MAE','AbsRel amplitude RMSE']):
        vals=[float(regression[n][key]) for n in names]
        ax.bar(range(6),vals,color=[COLORS.get(n,'#A8ACB0') for n in names],width=.7)
        ax.set_xticks(range(6),[LABELS.get(n,'Constant mean' if n=='CalibrationMeanAbsRel' else 'Constant median') for n in names],rotation=30,ha='right')
        ax.set_ylabel(title+' (lower better)');ax.set_ylim(0,max(vals)*1.2);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Calibration-only isotonic error mapping; both constant controls retained',fontsize=11);save(fig,'continuous_error_regression')
    rpb=csvread(out/'probability_reliability_bins.csv');fig,axes=plt.subplots(1,3,figsize=(10.7,3.4),layout='constrained')
    for ax,sid in zip(axes,['MVS_0001_0000','MVS_0001_0049','MVS_0001_0099']):
        ax.plot([0,1],[0,1],'--',color='.7',lw=1)
        for method in CORE:
            own=[r for r in rpb if r['view']==VIEW and r['sample_id']==sid and r['method']==method]
            ax.plot([float(r['predicted_probability']) for r in own],[float(r['observed_event_frequency']) for r in own],'o-',color=COLORS[method],label=LABELS[method],ms=4)
        ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mapped P(AbsRel > 0.2)',ylabel='Observed event fraction',title=sid)
    axes[-1].legend(fontsize=8);fig.suptitle('Sequence-separated diagnostic, not certified probability calibration',fontsize=10);save(fig,'probability_reliability')
    weather=csvread(out/'viper_weather_macro.csv');raw=csvread(out/'viper_raw_signal_statistics.csv');agreement=csvread(out/'signal_complementarity.csv');envs=['Day','Sunset','Rain','Snow','Night'];fig,axes=plt.subplots(1,3,figsize=(11.5,3.9),layout='constrained')
    for i,env in enumerate(envs):
        r=next(r for r in weather if r['view']==VIEW and r['environment']==env)
        own=[r for r in raw if r['view']==VIEW and r['environment']==env];ag=[r for r in agreement if r['view']==VIEW and r.get('environment')==env]
        for ax,key,rows,color in [(axes[0],'confidence_mean',own,COLORS['NativeOnly']),(axes[1],'flip_P95',own,COLORS['FlipOnly']),(axes[2],'high_low_conflict_fraction',ag,COLORS['RankFusion'])]:
            vals=[float(t[key]) for t in rows];ax.scatter(i+np.array([-.07,.07]),vals,s=30,color=color);ax.plot([i-.2,i+.2],[np.mean(vals)]*2,color=color,lw=2)
    for ax in axes:ax.set_xticks(range(5),envs,rotation=25);ax.grid(axis='y',alpha=.15)
    axes[0].set(title='Raw Native score mean',ylabel='Raw confidence (not probability)');axes[1].set(title='Flip disagreement P95',ylabel='Relative depth disagreement',yscale='log');axes[2].set(title='Opposed high / low risks',ylabel='Fraction of all image pixels')
    fig.suptitle('VIPER: two separated samples per weather; no admitted dense depth GT',fontsize=11);save(fig,'viper_weather_signals')
    # All actual score maps and RGBs, without substituting pseudo GT on VIPER.
    metadata=[]
    for row in records():
        item=row['sample'];sid=item['sample_id'];rgb=np.asarray(Image.open(row['local_rgb']).convert('RGB'))
        with np.load(out/'risk_maps'/(sid+'.npz'),allow_pickle=False) as z:
            fig=plt.figure(figsize=(12,5.5),layout='constrained')
            grid=fig.add_gridspec(2,4,width_ratios=[1,1,1,.035])
            ax=[fig.add_subplot(grid[i//3,i%3]) for i in range(6)]
            ax[0].imshow(rgb);ax[0].set_title('Input RGB · '+sid,fontsize=9)
            im=None
            for axis,key,title in zip(ax[1:5],['rank_native','rank_flip','risk_fusion','risk_max'],['Native risk percentile','Flip risk percentile','Equal-rank fusion','Max-risk fusion']):
                im=axis.imshow(z[key],cmap='magma',norm=Normalize(0,1),interpolation='nearest');axis.set_title(title)
            risk_axis=fig.add_subplot(grid[0,3] if 'AbsRel' in z else grid[:,3])
            cb=fig.colorbar(im,cax=risk_axis);cb.set_label('Relative risk, not probability',fontsize=8)
            if 'AbsRel' in z:
                cm=plt.get_cmap('magma').copy();cm.set_bad('#BDBDBD');err=ax[5].imshow(z['AbsRel'],cmap=cm,norm=Normalize(0,1),interpolation='nearest');ax[5].set_title('Actual AbsRel · display clips at 1');c=fig.colorbar(err,cax=fig.add_subplot(grid[1,3]));c.set_label('AbsRel; grey = invalid GT',fontsize=8)
            else:
                ax[5].text(.5,.52,'VIPER\nNo admitted dense depth GT\nNo accuracy/error map',ha='center',va='center',transform=ax[5].transAxes,fontsize=12);ax[5].set_facecolor('#F4F4F4')
            for axis in ax:axis.set_xticks([]);axis.set_yticks([])
            fig.suptitle('Common 0–1 risk display · aligned full image grids · frozen zero-extended view',fontsize=10)
            save(fig,'plate_'+sid,vector=False)
            metadata.append({'sample_id':sid,'original_RGB_sha256':item['rgb_sha256'],'score_maps_sha256':sha(out/'risk_maps'/(sid+'.npz')),'risk_color_range':[0,1],'error_display_range':[0,1] if 'AbsRel' in z else None,'no_GT_surrogate':True})
    dump(TASK/'figures/FIGURE_SOURCE_INDEX.json',metadata);cpu_assert();print('ALL_RESULT_FIGURES_RENDERED',len(list(dest.glob('*.png'))),flush=True)

if __name__=='__main__':main()
