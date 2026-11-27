"""Actual paired VO figures; one global alignment per window/method."""
import csv,json,os
from pathlib import Path
os.environ['MPLCONFIGDIR']='D:/aaa/caches/matplotlib/task011b'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import TASK,dump
from evaluate_viper import legacy

plt.rcParams.update({'font.family':'sans-serif','font.size':8,'svg.fonttype':'none','pdf.fonttype':42,
    'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False})
COLORS=['#555555','#999999','#487FA5','#4E9C9B','#6A9C59','#C2914D','#946EB0']


def save(fig,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg','pdf'):fig.savefig(str(path)+'.'+ext,dpi=180,facecolor='white')
    plt.close(fig)


def main():
    e=TASK/'evaluation';out=TASK/'figures/vo';out.mkdir(parents=True,exist_ok=True)
    rows=list(csv.DictReader((e/'VIPER_TRAJECTORY_METRICS.csv').open()))
    by={(r['window'],r['arm']):r for r in rows}
    windows=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,key,title in zip(axes.ravel(),['ate_sim3_path_pct','single_global_sim3_RPE_translation','single_global_sim3_RPE_rotation_deg','raw_path_ratio_abs_error'],
        ['Sim3 ATE / GT path (%) ↓','Single-scale translation RPE ↓','Rotation RPE (degrees) ↓','Raw path ratio absolute error ↓']):
        for arm in range(7):
            own=[float(r[key]) for r in rows if r['arm']=='A'+str(arm) and r.get(key) not in ('',None)]
            if own:
                ax.scatter(np.full(len(own),arm),own,c=COLORS[arm],s=12,alpha=.5)
                ax.plot([arm-.22,arm+.22],[np.median(own)]*2,c=COLORS[arm],lw=2.5)
        ax.set(xticks=range(7),xticklabels=['A'+str(i) for i in range(7)],title=title)
        ax.grid(axis='y',alpha=.15)
    fig.suptitle('Fixed20 VIPER windows, seed43 — dots=sequences, bars=medians; missing scores are reported failures',fontsize=10)
    save(fig,out/'method_distributions')
    envs=['Day','Sunset','Rain','Snow','Night']
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    matrix=np.full((5,7),np.nan);success=np.zeros((5,7))
    for i,env in enumerate(envs):
        for arm in range(7):
            own=[r for r in rows if r['environment']==env and r['arm']=='A'+str(arm)]
            v=[float(r['ate_sim3_path_pct']) for r in own if r.get('ate_sim3_path_pct') not in ('',None)]
            if v:matrix[i,arm]=np.median(v)
            success[i,arm]=sum(r['success']=='True' for r in own)/4
    for ax,data,title in zip(axes,[matrix,success],['Median Sim3 ATE / path (%) ↓','Complete valid trajectory fraction ↑']):
        im=ax.imshow(data,cmap='viridis',aspect='auto')
        ax.set(xticks=range(7),xticklabels=['A'+str(j) for j in range(7)],yticks=range(5),yticklabels=envs,title=title)
        for i in range(5):
            for j in range(7):ax.text(j,i,f'{data[i,j]:.2f}' if np.isfinite(data[i,j]) else 'NA',ha='center',va='center',color='white',fontsize=8)
        fig.colorbar(im,ax=ax,shrink=.8)
    save(fig,out/'environment_results')
    for w in windows:
        with np.load(w['offline_gt'],allow_pickle=False) as z:gt=z['gt_c2w'][:,:3,3].copy()
        _,_,vh=np.linalg.svd(gt-gt.mean(0),full_matrices=False);basis=vh[:2].T
        fig,axes=plt.subplots(1,2,figsize=(10.5,4.8),layout='constrained')
        for ax in axes:
            xy=(gt-gt[0])@basis;ax.plot(xy[:,0],xy[:,1],c='black',lw=2,label='Camera GT')
        for arm in range(7):
            r=by.get((w['window_id'],'A'+str(arm)))
            if not r or r.get('ate_sim3_rmse') in ('',None):continue
            root=TASK/'gpu_results/raw'/('window_'+w['window_id']+'_A'+str(arm))/'result'
            with np.load(root/'trajectory.npz',allow_pickle=False) as z:pos=z['c2w_xyzw'][:,:3].copy()
            for ax,scaled in zip(axes,[False,True]):
                q,t,s,_=legacy.fit_alignment(pos,gt,scaled)
                xy=(s*(pos@q.T)+t-gt[0])@basis
                ax.plot(xy[:,0],xy[:,1],c=COLORS[arm],lw=1,ls='--' if arm==1 else '-',label='A'+str(arm))
        for ax,title in zip(axes,['Rigid alignment; original scale retained','One global Sim3 scale; shape only']):
            ax.set(title=title,xlabel='GT-PCA1 (native units)',ylabel='GT-PCA2 (native units)');ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.15)
        axes[1].legend(ncol=4,fontsize=7)
        fig.suptitle(w['window_id']+' / '+w['environment'],fontsize=10)
        save(fig,out/'trajectories'/w['window_id'])
    dump(out/'FIGURE_INVENTORY.json',dict(source='Actual finalized trajectory CSV/NPZ only',windows=len(windows),
        png=len(list(out.rglob('*.png'))),one_global_scale_per_trajectory=True,no_segment_scale_refit=True))


if __name__=='__main__':main()
