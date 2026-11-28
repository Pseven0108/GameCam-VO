"""CPU-only complete-case comparison; no model, GPU or remote access."""
import csv,json,pathlib,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
sys.path.insert(0,str(TASK/'src'))
from evaluation import evaluate

def main():
    out=TASK/'evaluation';out.mkdir(exist_ok=False)
    with np.load(TASK/'data/train_004_01658-01721/offline_gt.npz',allow_pickle=False) as gt:
        ids=gt['rgb_ids'].copy();truth=gt['gt_c2w'].copy()
    rows=[];arrays={};fits=[];inactive=[]
    for run in sorted((TASK/'outputs').glob('*_???')):
        if not (run/'CANDIDATE_NOT_ACTIVE.json').exists():continue
        with np.load(run/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise RuntimeError('Inactive attempt RGB identity mismatch')
            stats,_=evaluate(z['c2w'].astype(np.float64),truth.astype(np.float64),ids)
        inactive.append(dict(attempt=run.name,status='INACTIVE_CANDIDATE_ENGINEERING_ATTEMPT',
            role='Observed identity-fallback result; not an active scale intervention',**stats))
    for arm in ['BASE','A5','SCALE','SCALE_A5']:
        attempts=sorted((TASK/'outputs').glob(arm+'_???'))
        attempts=[p for p in attempts if (p/'COMPLETE.json').exists() and not (p/'CANDIDATE_NOT_ACTIVE.json').exists()]
        if len(attempts)>1:raise RuntimeError('Multiple completed attempts: no selective reporting')
        if not attempts:rows.append(dict(arm=arm,status='NOT_COMPLETED'));continue
        run=attempts[0];meta=json.loads((run/'COMPLETE.json').read_text())
        with np.load(run/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise RuntimeError('RGB/GT ID pairing differs')
            stats,arr=evaluate(z['c2w'].astype(np.float64),truth.astype(np.float64),ids)
        events=[json.loads(x) for x in (run/'BA_CALLS.jsonl').read_text().splitlines()]
        scale_events=[x for x in events if x['scale_active']]
        for e in events:
            for fit in e['fit_records']:fits.append(dict(arm=arm,call=e['call'],rgb_id=1658+fit['timestamp'],**fit))
        kf=np.load(run/'keyframe_state.npz',allow_pickle=False)['timestamps'].astype(int)
        row=dict(arm=arm,status='COMPLETE',attempt=run.name,frames=64,keyframes=meta['keyframes'],
            runtime_seconds=meta['seconds'],peak_reserved_GiB=meta['peak_reserved_bytes']/1024**3,
            peak_allocated_GiB=meta['peak_allocated_bytes']/1024**3,
            local_scale_ba_calls=len(scale_events),a5_ba_calls=sum(x['a5_active'] for x in events),**stats)
        rows.append(row);arrays[arm]=arr
        np.savez_compressed(out/(arm+'_aligned.npz'),rgb_ids=ids,keyframe_rgb_ids=1658+kf,**arr)
    baseline=next((r for r in rows if r['arm']=='BASE' and r['status']=='COMPLETE'),None)
    if baseline:
        for row in rows:
            if row['status']=='COMPLETE':
                row['ate_sim3_change_vs_BASE_percent']=100*(row['ate_sim3_rmse']/baseline['ate_sim3_rmse']-1)
    def save_csv(path,records):
        keys=list(dict.fromkeys(k for r in records for k in r))
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(records)
    save_csv(out/'FOUR_ARM_METRICS.csv',rows);save_csv(out/'SCALE_FITS.csv',fits)
    save_csv(out/'INACTIVE_CANDIDATE_ATTEMPTS.csv',inactive)
    (out/'RESULTS.json').write_text(json.dumps(dict(results=rows,
        units='VIPER game units; metres not asserted',alignment='one global Sim3 per complete window',
        inactive_engineering_attempts=inactive,
        study='one Train Day004 64-frame development window, one seed43; no generalization claim'),indent=2)+'\n')
    fig,ax=plt.subplots(1,2,figsize=(11,4.5));gp=truth[:,:3,3]
    # Plot the ground-plane axes with the largest GT variation.
    dims=np.argsort(np.var(gp,axis=0))[-2:]
    ax[0].plot(gp[:,dims[0]],gp[:,dims[1]],'k--',label='GT')
    for arm,arr in arrays.items():
        p=arr['aligned_positions'];ax[0].plot(p[:,dims[0]],p[:,dims[1]],label=arm)
        ax[1].plot(ids,arr['position_errors'],label=arm)
    ax[0].set(xlabel=f'Axis {dims[0]} (game units)',ylabel=f'Axis {dims[1]} (game units)',title='One global Sim3 per complete trajectory')
    ax[0].axis('equal');ax[1].set(xlabel='Original RGB frame ID',ylabel='Position error (game units)',title='Offline GT errors')
    for a in ax:a.grid(alpha=.2);a.legend(fontsize=8)
    fig.suptitle('Local RTX 5060: isolated DROID-W scale-alignment candidate')
    fig.tight_layout();fig.savefig(out/'FOUR_ARM_TRAJECTORIES.png',dpi=160);fig.savefig(out/'FOUR_ARM_TRAJECTORIES.pdf');plt.close(fig)
    if fits:
        fig,ax=plt.subplots(figsize=(8,4))
        for arm in ['SCALE','SCALE_A5']:
            accepted=[f for f in fits if f['arm']==arm and f['accepted']]
            ax.scatter([r['rgb_id'] for r in accepted],[r['scale'] for r in accepted],s=9,alpha=.35,label=arm)
        ax.axhline(1,color='black',linestyle='--');ax.set(xlabel='Fitted keyframe RGB ID',ylabel='Disparity prior multiplier',title='Estimated-map alignment; this is not metric calibration')
        ax.legend();fig.tight_layout();fig.savefig(out/'SCALE_FIT_DISTRIBUTION.png',dpi=160);plt.close(fig)
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
