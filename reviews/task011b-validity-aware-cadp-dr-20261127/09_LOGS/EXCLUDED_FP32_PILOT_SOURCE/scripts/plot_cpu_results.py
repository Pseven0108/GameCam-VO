"""Actual R0/R1 figures only; no illustrative VO improvements or simulated runs."""
import csv
import json
import os
from pathlib import Path

os.environ['MPLCONFIGDIR']='D:/aaa/caches/matplotlib/task011b'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
from PIL import Image

from common import TASK,records,dump

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':8,
    'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
    'legend.frameon':False,'axes.linewidth':.7})
METHODS=['NativeOnly','FlipOnly','RankFusion','MaxFusion','ValidityAwareFusion']
LABELS=['Native','Flip','Rank','Max','Validity-aware']
COLORS=['#777777','#4B7EAA','#52987B','#C08D52','#8E70AC']
RUN=TASK/'runs/cpu_003'
OUT=TASK/'figures'


def read(name):return list(csv.DictReader((RUN/name).open(encoding='utf-8-sig')))


def save(fig,path,vector=True):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(str(path)+'.png',dpi=190,facecolor='white')
    if vector:
        fig.savefig(str(path)+'.svg',facecolor='white');fig.savefig(str(path)+'.pdf',facecolor='white')
    plt.close(fig)


def metrics_figure(domain,name):
    rows=[r for r in read('RELIABILITY_METHOD_COMPARISON.csv') if r['sequence']=='0001' and r['disagreement']=='SymmetricRelative' and r['domain']==domain]
    keys=['AUROC_gt_0.2','AP_gt_0.2','AUSE','Spearman']
    titles=['High-error AUROC (AbsRel > 0.2) ↑','High-error AP (AbsRel > 0.2) ↑','Raw AbsRel AUSE ↓','Error–risk Spearman ↑']
    fig,axes=plt.subplots(1,4,figsize=(12.6,3.7),layout='constrained')
    for ax,key,title in zip(axes,keys,titles):
        for i,method in enumerate(METHODS):
            values=[float(r[key]) for r in rows if r['method']==method]
            ax.scatter(np.full(len(values),i),values,c=COLORS[i],s=18,alpha=.75)
            ax.plot([i-.23,i+.23],[np.mean(values)]*2,c=COLORS[i],lw=2.4)
        ax.set(xticks=range(5),xticklabels=LABELS,title=title)
        ax.tick_params(axis='x',rotation=32);ax.grid(axis='y',alpha=.18)
        ax.set_xlim(-.5,4.5)
    fig.suptitle(('Full-GT rejection-policy diagnostic' if domain.startswith('FULL') else 'Common-valid-pair diagnostic (not a strict-GT pass)')+'\nThree frames, one previously observed MVS sequence; dots = frames, lines = means',fontsize=10)
    save(fig,OUT/name)


def main():
    OUT.mkdir(exist_ok=True)
    metrics_figure('FULL_GT_ZERO_EXTENDED_REJECTION_POLICY','ranking_full_gt')
    metrics_figure('COMMON_VALID_PAIR_DIAGNOSTIC_NOT_GATE_PASS','ranking_common_pair')
    curves=[r for r in read('RISK_COVERAGE_COMPARISON.csv') if r['sequence']=='0001' and r['domain'].startswith('FULL')]
    fig,ax=plt.subplots(figsize=(7.6,4.8),layout='constrained')
    for i,method in enumerate(METHODS):
        own=[r for r in curves if r['method']==method]
        x=np.array(sorted({float(r['coverage']) for r in own}))
        y=[np.mean([float(r['risk']) for r in own if float(r['coverage'])==c]) for c in x]
        ax.plot(x,y,color=COLORS[i],label=LABELS[i],lw=1.5)
    own=[r for r in curves if r['method']=='NativeOnly'];x=np.array(sorted({float(r['coverage']) for r in own}))
    ax.plot(x,[np.mean([float(r['oracle']) for r in own if float(r['coverage'])==c]) for c in x],c='#333333',ls='--',label='Oracle')
    ax.set(xlabel='Retained low-risk coverage',ylabel='Mean AbsRel after frozen scale',title='Full-GT policy diagnostic: zero predictions retained')
    ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.2)
    save(fig,OUT/'risk_coverage_full_gt')
    rows=read('TTA_DISAGREEMENT_COMPARISON.csv')
    groups=['HistoricalUngatedRelative','LegacyRelative','SymmetricRelative','LogDisagreement']
    weather_colors=dict(zip(['Day','Sunset','Rain','Snow','Night'],['#4B7EAA','#C08D52','#52987B','#B0718E','#8E70AC']))
    fig,axes=plt.subplots(1,2,figsize=(10.6,4.3),layout='constrained')
    for i,key in enumerate(groups):
        for environment,offset in zip(['Day','Sunset','Rain','Snow','Night'],np.linspace(-.24,.24,5)):
            values=[max(float(r['q1']),1e-12) for r in rows if r['dataset']=='VIPER' and r['environment']==environment and r['disagreement']==key]
            axes[0].scatter(np.full(len(values),i+offset),values,s=18,color=weather_colors[environment],label=environment if i==0 else None)
    axes[0].set_yscale('log');axes[0].set(xticks=range(4),xticklabels=['Historical\nungated T1','Pair-valid\nT1','Pair-valid\nT2','Pair-valid\nT3'],ylabel='Per-image maximum (log scale)',title='Numerical extremes; populations differ as labelled')
    axes[0].legend(ncol=2,fontsize=7)
    audit=read('TTA_VALIDITY_AUDIT.csv')
    vip=[r for r in audit if r['dataset']=='VIPER']
    x=np.arange(len(vip));a=np.array([int(r['native_invalid']) for r in vip]);b=np.array([int(r['native_valid_pair_invalid']) for r in vip])
    axes[1].bar(x,a,color='#626C83',label='Native invalid (prior off)')
    axes[1].bar(x,b,bottom=a,color='#C89C63',label='Native valid, TTA invalid (fallback)')
    axes[1].set(xticks=x,xticklabels=[r['environment']+'\n'+r['sample'].split('_')[-1] for r in vip],ylabel='Pixels',title='Ten cached VIPER images (not continuous frames)')
    axes[1].tick_params(axis='x',rotation=32,labelsize=6);axes[1].legend(fontsize=7)
    save(fig,OUT/'tta_numerical_validity')
    # Images: all 16 records, with one common plotting range per displayed field.
    for record in records():
        sample=record['sample'];sid=sample['sample_id']
        with Image.open(record['local_rgb']) as im:rgb=np.asarray(im.convert('RGB'))
        with np.load(RUN/'derived_maps'/(sid+'.npz'),allow_pickle=False) as z:maps={k:z[k].copy() for k in z.files}
        native=maps['native_depth'].astype(float);flip=maps['flip_aligned_depth'].astype(float)
        legacy=np.abs(native-flip)/(np.abs(native)+1e-6)
        states=np.zeros(native.shape);states[~maps['pair_valid']]=1;states[~maps['native_valid']]=2
        fig=plt.figure(figsize=(12.5,6.8),layout='constrained');gs=fig.add_gridspec(2,4)
        ax=fig.add_subplot(gs[0,0]);ax.imshow(rgb);ax.set_title('Original RGB');ax.axis('off')
        panels=[(states,'Validity: white=pair valid\nyellow=fallback; dark=prior off',ListedColormap(['#fafafa','#e6b55b','#4e5567']),0,2),
            (np.log10(1+legacy),'Historical log10(1+T1)\ndisplay range [0,8]','magma',0,8),
            (maps['tta_SymmetricRelative'],'Pair-valid symmetric T2\nundefined pixels grey','viridis',0,1),
            (maps['tta_LogDisagreement'],'Pair-valid log T3\ndisplay clipped at 4','magma',0,4),
            (maps['RankFusion_risk'],'Pair-only equal-rank risk\nundefined pixels grey','viridis',0,1),
            (maps['ValidityAwareFusion_risk'],'Validity-aware rank risk\nNative-only fallback; grey=off','viridis',0,1),
            (maps['ValidityAwareFusion_reliability'],'Prior reliability coefficient\ninvalid Native exactly zero','viridis',0,1)]
        for i,(field,title,cmap,vmin,vmax) in enumerate(panels,1):
            ax=fig.add_subplot(gs[i//4,i%4]);cmap=plt.get_cmap(cmap).copy() if isinstance(cmap,str) else cmap
            cmap.set_bad('#bdbdbd');image=ax.imshow(field,cmap=cmap,vmin=vmin,vmax=vmax)
            ax.set_title(title,fontsize=8);ax.axis('off')
            fig.colorbar(image,ax=ax,fraction=.045,pad=.02,shrink=.75,ticks=[0,1,2] if i==1 else None)
        fig.suptitle(sid+' — numerical/control behavior, not measured VIPER accuracy',fontsize=11)
        save(fig,OUT/'validity_plates'/sid,False)
    dump(OUT/'FIGURE_INVENTORY.json',dict(PNG=len(list(OUT.rglob('*.png'))),SVG=len(list(OUT.glob('*.svg'))),
        PDF=len(list(OUT.glob('*.pdf'))),backend='matplotlib',all_data_from_actual_cpu_003=True,VO_results_plotted=False))
    print('ACTUAL_CPU_FIGURES_COMPLETE',flush=True)


if __name__=='__main__':main()
