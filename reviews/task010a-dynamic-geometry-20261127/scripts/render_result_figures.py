"""Plot actual paired runs, per-window units and individual seed variation."""
import json
import os
from pathlib import Path
os.environ['MPLCONFIGDIR']='D:/aaa/caches/task010a/matplotlib'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
OUT=TASK/'08_reports/figures'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})


def main():
    rows=json.loads((TASK/'07_cross_scene_evaluation/ALL_RUN_METRICS.json').read_text())
    rows=[r for r in rows if r['status']=='COMPLETE' and r['run']!='night007_dev_baseline_s43_r1']
    roster={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
    order=['baseline','legacy','legacy_mean','neutral','gmos','geomotion','geomotion_full','geometry','fusion','static','fusion_static','depth','depth_static','depth_fusion']
    fig,ax=plt.subplots(figsize=(12,4.5),layout='constrained')
    for i,method in enumerate(order):
        values=[r['sim3_ate_native_reference_units'] for r in rows if r['dataset']=='night007_dev' and r['method']==method]
        if not values:continue
        color='#1b718e' if method in ['baseline','geometry','depth'] else '#8a8c91'
        offset=np.linspace(-.12,.12,len(values))
        ax.scatter(np.full(len(values),i)+offset,values,s=25,color=color,zorder=3)
        ax.errorbar(i,np.mean(values),yerr=np.std(values,ddof=1) if len(values)>1 else 0,color=color,capsize=3,linewidth=1)
    ax.set_xticks(range(len(order)),order,rotation=35,ha='right')
    ax.set(ylabel='Whole-window Sim3 ATE (VIPER game units)',title='Night007 development: each dot is one seed; bars show sample SD')
    ax.grid(axis='y',alpha=.15);fig.savefig(OUT/'development_seed_comparison.png',dpi=160);plt.close(fig)
    selection_path=TASK/'09_reproducibility/TRANSFER_SELECTION_FROZEN.json'
    if not selection_path.exists():return
    selection=json.loads(selection_path.read_text());candidate=selection['main_confirmatory_candidate']
    names=selection['heldout_windows'];game=[d for d in names if roster[d]['domain']=='VIPER_GAME'];real=[d for d in names if d not in game]
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained',gridspec_kw={'width_ratios':[2,1]})
    for ax,group,unit in zip(axes,[game,real],['VIPER game units','Published reference metres']):
        for offset,method,color in [(-.15,'baseline','#72777f'),(.15,candidate,'#087f8c')]:
            for i,name in enumerate(group):
                rr=[r for r in rows if r['dataset']==name and r['method']==method]
                if not rr:continue
                x=np.array([r['sim3_ate_native_reference_units'] for r in rr])
                ax.scatter(np.full(len(x),i+offset)+np.linspace(-.035,.035,len(x)),x,s=22,color=color,label=method if i==0 else None)
                ax.errorbar(i+offset,x.mean(),yerr=x.std(ddof=1) if len(x)>1 else 0,color=color,capsize=3)
        ax.set_xticks(range(len(group)),[n.replace('_holdout','') for n in group],rotation=25,ha='right')
        ax.set(ylabel=f'Sim3 ATE ({unit})',title='Frozen held-out comparison')
        ax.grid(axis='y',alpha=.15);ax.legend(fontsize=8)
    fig.savefig(OUT/'heldout_baseline_candidate.png',dpi=160);plt.close(fig)
    for name,d in roster.items():
        if name=='wildworld_thirdperson_qual':continue
        candidates=['baseline',candidate,selection['best_dynamic_candidate'],selection['best_fusion_candidate'],'legacy']
        candidates=list(dict.fromkeys(candidates));curves=[]
        for method in candidates:
            rr=[r for r in rows if r['dataset']==name and r['method']==method and r['seed']==43]
            if not rr:continue
            r=rr[0];path=TASK/'07_cross_scene_evaluation'/(r['run']+'_aligned.npz')
            with np.load(path,allow_pickle=False) as z:curves.append((method,z['c2w'].copy(),z['per_frame_error'].copy()))
        if not curves:continue
        with np.load(d['offline_gt'],allow_pickle=False) as z:truth=z['c2w'];ids=z['rgb_ids']
        center=truth[:,:3,3].mean(0);_,_,basis=np.linalg.svd(truth[:,:3,3]-center)
        reference=(truth[:,:3,3]-center)@basis[:2].T
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        axes[0].plot(*reference.T,color='black',label='Reference',linewidth=2)
        for method,curve,error in curves:
            xy=(curve[:,:3,3]-center)@basis[:2].T
            axes[0].plot(*xy.T,label=method);axes[1].plot(ids,error,label=method)
        axes[0].set(xlabel='Reference-PC1',ylabel='Reference-PC2',title=f'{name}: one global Sim3 / seed43');axes[0].axis('equal')
        axes[1].set(xlabel='Original RGB ID',ylabel='Position error ('+d['pose_unit']+')',title='No interval scale refitting')
        for ax in axes:ax.legend(fontsize=7);ax.grid(alpha=.12)
        fig.savefig(OUT/(name+'_trajectory.png'),dpi=150);plt.close(fig)
    print('Rendered measured seed/transfer/trajectory figures')


if __name__=='__main__':main()
