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
    scored_windows=len({r['window'] for r in rows if r.get('ate_sim3_path_pct') not in ('',None)})
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
    fig.suptitle(f'Fixed20 VIPER windows, seed43 — dots=sequences, bars=medians; ATE N={scored_windows}\nUndefined alignment scores are unscored; all failure/completion outcomes remain in CSV',fontsize=9)
    save(fig,out/'method_distributions')
    envs=['Day','Sunset','Rain','Snow','Night']
    fig,axes=plt.subplots(1,2,figsize=(10,4.5),layout='constrained')
    matrix=np.full((5,7),np.nan);success=np.full((5,7),np.nan)
    for i,env in enumerate(envs):
        for arm in range(7):
            own=[r for r in rows if r['environment']==env and r['arm']=='A'+str(arm)]
            v=[float(r['ate_sim3_path_pct']) for r in own if r.get('ate_sim3_path_pct') not in ('',None)]
            if v:matrix[i,arm]=np.median(v)
            if len(own)==4:success[i,arm]=sum(r['success']=='True' for r in own)/4
    for ax,data,title in zip(axes,[matrix,success],['Median Sim3 ATE / path (%) ↓','Complete valid trajectory fraction ↑']):
        im=ax.imshow(data,cmap='viridis',aspect='auto',**({'vmin':0,'vmax':1} if data is success else {}))
        ax.set(xticks=range(7),xticklabels=['A'+str(j) for j in range(7)],yticks=range(5),yticklabels=envs,title=title)
        for i in range(5):
            for j in range(7):
                value=data[i,j]
                color='black' if np.isfinite(value) and im.norm(value)>.58 else ('#333333' if not np.isfinite(value) else 'white')
                ax.text(j,i,f'{value:.2f}' if np.isfinite(value) else 'NA',ha='center',va='center',color=color,fontsize=8)
        fig.colorbar(im,ax=ax,shrink=.8)
    fig.suptitle('All20 planned windows; accuracy conditions on available scores\nUndefined near-zero alignment scores remain NA; completion keeps the full denominator',fontsize=9)
    save(fig,out/'environment_results')
    paired=list(csv.DictReader((e/'VIPER_METHOD_COMPARISON.csv').open()))
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,key,title in zip(axes.ravel(),
        ['ate_sim3_path_pct','raw_path_ratio_abs_error','single_global_sim3_RPE_rotation_deg','runtime_tracking_child_seconds'],
        ['Paired Sim3 ATE / path difference (pp) ↓','Paired raw path-ratio error difference ↓',
         'Paired rotation RPE difference (degrees) ↓','Paired tracker time difference (seconds) ↓']):
        for i,arm in enumerate(['A1','A2','A3','A4','A5','A6']):
            for reference,shift,marker in [('A0',-.12,'o'),('A1',.12,'s')]:
                r=next((r for r in paired if r['arm']==arm and r['reference']==reference and r['metric']==key),None)
                if r is None:continue
                x=float(r['mean_difference']);lo=r['lower95'];hi=r['upper95']
                err=np.array([[x-float(lo)],[float(hi)-x]]) if lo and hi else None
                ax.errorbar(x,i+shift,xerr=err,fmt=marker,ms=5,c=COLORS[int(arm[1])],
                    capsize=2,label=reference if i==1 else None)
        ax.axvline(0,c='#777777',lw=.8,ls='--')
        ax.set(yticks=range(6),yticklabels=['A1','A2','A3','A4','A5','A6'],title=title)
        ax.grid(axis='x',alpha=.15)
    axes[0,0].legend(title='Reference',fontsize=7)
    fig.suptitle('Means and sequence-bootstrap 95% intervals; one seed; available-pair N in CSV\nUnscored near-zero alignments are retained as missing, not assigned an error of zero',fontsize=9)
    save(fig,out/'paired_differences')
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
            failed=[a for a in ('A0','A1','A2','A3','A4','A5','A6') if
                    by.get((w['window_id'],a),{}).get('success')=='False']
            if failed:
                ax.text(.02,.02,'Failed: '+', '.join(failed),transform=ax.transAxes,
                        fontsize=7,va='bottom',bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
            unscored=[a for a in ('A0','A1','A2','A3','A4','A5','A6') if
                      by.get((w['window_id'],a),{}).get('success')=='True' and
                      by.get((w['window_id'],a),{}).get('ate_sim3_rmse') in ('',None)]
            if unscored:
                ax.text(.02,.02,'Complete, alignment undefined: '+', '.join(unscored),
                        transform=ax.transAxes,fontsize=7,va='bottom',
                        bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
            if np.max(np.linalg.norm(gt-gt[0],axis=1))<1e-6:
                ax.text(.02,.98,'Near-zero GT translation; displayed variation is numerical jitter',
                        transform=ax.transAxes,fontsize=7,va='top',
                        bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
        axes[1].legend(ncol=4,fontsize=7)
        fig.suptitle(w['window_id']+' / '+w['environment'],fontsize=10)
        save(fig,out/'trajectories'/w['window_id'])
    dump(out/'FIGURE_INVENTORY.json',dict(source='Actual finalized trajectory CSV/NPZ only',windows=len(windows),
        png=len(list(out.rglob('*.png'))),one_global_scale_per_trajectory=True,no_segment_scale_refit=True))


if __name__=='__main__':main()
