"""Labelled sensitivity figures; no removal of original whole-batch plots."""
import csv
import numpy as np
from common import TASK,dump
from plot_viper_results import plt,save,COLORS


def main():
    e=TASK/'evaluation'
    with (e/'VIPER_MOTION_STRATIFIED_RUNS.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    with (e/'VIPER_MOTION_STRATIFIED_PAIRED.csv').open(encoding='utf-8-sig',newline='') as f:
        paired=list(csv.DictReader(f))
    own=[r for r in rows if r['motion_stratum']=='TRANSLATING']
    if len(rows)!=140:raise RuntimeError('Final sensitivity plots require full batch')
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    fields=('ate_sim3_path_pct','raw_path_ratio_abs_error','single_global_sim3_RPE_rotation_deg','runtime_tracking_child_seconds')
    titles=('Sim3 ATE / GT path (%) ↓','Raw path-ratio absolute error ↓','Rotation RPE (degrees) ↓','Tracking child time (seconds) ↓')
    for ax,key,title in zip(axes.ravel(),fields,titles):
        for i in range(7):
            values=[float(r[key]) for r in own if r['arm']=='A'+str(i) and r.get(key) not in ('',None)]
            ax.scatter(np.full(len(values),i),values,c=COLORS[i],s=15,alpha=.55)
            if values:ax.plot([i-.2,i+.2],[np.median(values)]*2,c=COLORS[i],lw=2.3)
        ax.set(xticks=range(7),xticklabels=['A'+str(i) for i in range(7)],title=title)
        ax.grid(axis='y',alpha=.15)
    n=len({r['window'] for r in own})
    fig.suptitle(f'Exploratory GT-motion sensitivity: {n} translating windows; original20-window results retained',fontsize=10)
    save(fig,TASK/'figures/vo/motion_sensitivity/distributions_translating')
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,key,title in zip(axes.ravel(),fields,titles):
        for i,arm in enumerate(('A2','A3','A4','A5','A6')):
            for base,shift,marker in [('A0',-.13,'o'),('A1',.13,'s')]:
                r=next((r for r in paired if r['motion_stratum']=='TRANSLATING' and
                    r['arm']==arm and r['reference']==base and r['metric']==key),None)
                if not r:continue
                x=float(r['mean_difference']);low=r['lower95'];high=r['upper95']
                ax.plot(x,i+shift,marker=marker,ms=5,c=COLORS[int(arm[1])],ls='none',
                        label=base if i==0 else None)
                if low and high:
                    ax.plot([float(low),float(high)],[i+shift,i+shift],c=COLORS[int(arm[1])],lw=1)
                    ax.plot([float(low)]*2,[i+shift-.035,i+shift+.035],c=COLORS[int(arm[1])],lw=1)
                    ax.plot([float(high)]*2,[i+shift-.035,i+shift+.035],c=COLORS[int(arm[1])],lw=1)
        ax.axvline(0,c='#777777',lw=.8,ls='--')
        ax.set(yticks=range(5),yticklabels=['A2','A3','A4','A5','A6'],title='Paired difference: '+title)
        ax.grid(axis='x',alpha=.15)
    axes[0,0].legend(title='Reference',fontsize=7)
    fig.suptitle('Post-selection sensitivity, not a confirmatory endpoint; sequence-bootstrap95% intervals, N in CSV',fontsize=10)
    save(fig,TASK/'figures/vo/motion_sensitivity/paired_differences_translating')
    dump(TASK/'figures/vo/motion_sensitivity/FIGURE_SCOPE.json',dict(
        actual_formal_outcomes=140,translating_windows=n,exploratory_post_selection_sensitivity=True,
        original_figures_and_metric_rows_preserved=True,missing_metrics_not_imputed=True))
    print('ACTUAL_MOTION_SENSITIVITY_FIGURES',n,flush=True)


if __name__=='__main__':main()
