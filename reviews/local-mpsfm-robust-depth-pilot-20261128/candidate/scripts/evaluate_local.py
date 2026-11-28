"""CPU-only offline comparison, all four arms retained regardless of outcome."""
import csv,json,pathlib,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate';sys.path.insert(0,str(TASK/'src'))
from evaluation import evaluate
def csvout(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def main():
    out=TASK/'evaluation';out.mkdir(exist_ok=False)
    with np.load(TASK/'data/train_004_01658-01721/offline_gt.npz',allow_pickle=False) as g:
        ids=g['rgb_ids'].copy();truth=g['gt_c2w'].astype(np.float64)
    rows=[];arrays={};kfs={};trace_rows=[]
    for arm in ['BASE','A5','ROBUST','ROBUST_A5']:
        p=TASK/'outputs'/f'{arm}_001';meta=json.loads((p/'COMPLETE.json').read_text())
        with np.load(p/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise RuntimeError('Pose/GT frame mapping differs')
            metrics,arr=evaluate(z['c2w'].astype(np.float64),truth,ids)
        events=[json.loads(x) for x in (p/'BA_CALLS.jsonl').read_text().splitlines()]
        kf=np.load(p/'keyframe_state.npz',allow_pickle=False)['timestamps'].astype(int)
        kfs[arm]=(1658+kf).tolist();arrays[arm]=arr
        robust=[e for e in events if e['robust_active']]
        for e in robust:
            for it,items in enumerate(e['robust_iteration_trace']):
                for item in items:
                    slot=int(item[0]);row=dict(arm=arm,call=e['call'],rgb_id=1658+e['local_input_timestamp'],iteration=it+1,
                        keyframe_rgb_id=1658+e['keyframe_input_indices'][slot],valid_pixels=item[1],mean_q=item[2],min_q=item[3],
                        fraction_q_lt_01=item[4],fraction_q_lt_05=item[5],prior_rhs_l2=item[6],mean_prior_curvature=item[7],
                        mean_eta_damping=item[8],prior_objective=item[9]);trace_rows.append(row)
        row=dict(arm=arm,status='COMPLETE',attempt=p.name,frames=meta['frames'],keyframes=meta['keyframes'],
            runtime_seconds=meta['seconds'],peak_allocated_GiB=meta['peak_allocated_bytes']/1024**3,
            peak_reserved_GiB=meta['peak_reserved_bytes']/1024**3,robust_ba_calls=len(robust),
            a5_ba_calls=sum(e['a5_active'] for e in events),negative_before_clamp_event_pixel_sum=sum(e['negative_before_clamp'] for e in events),
            below_floor_event_pixel_sum=sum(e['clamp_below_1e5'] for e in events),**metrics)
        rows.append(row);np.savez_compressed(out/(arm+'_aligned.npz'),rgb_ids=ids,keyframe_rgb_ids=kfs[arm],**arr)
    by={r['arm']:r for r in rows}
    for r in rows:
        r['ate_change_vs_BASE_percent']=100*(r['ate_sim3_rmse']/by['BASE']['ate_sim3_rmse']-1)
        r['ate_change_vs_A5_percent']=100*(r['ate_sim3_rmse']/by['A5']['ate_sim3_rmse']-1)
    compare=[]
    for arm in ['A5','ROBUST','ROBUST_A5']:
        a,b=set(kfs['BASE']),set(kfs[arm]);compare.append(dict(reference='BASE',arm=arm,jaccard=len(a&b)/len(a|b),
            shared=len(a&b),base_only=sorted(a-b),candidate_only=sorted(b-a)))
    csvout(out/'FOUR_ARM_METRICS.csv',rows);csvout(out/'ROBUST_ITERATIONS.csv',trace_rows)
    (out/'KEYFRAME_COMPARISON.json').write_text(json.dumps(dict(ids=kfs,pairs=compare),indent=2)+'\n')
    decision=dict(robust_beats_BASE=by['ROBUST']['ate_sim3_rmse']<by['BASE']['ate_sim3_rmse'],
        combined_beats_A5=by['ROBUST_A5']['ate_sim3_rmse']<by['A5']['ate_sim3_rmse'],
        units='VIPER game units, not established metres',scope='one Train development window, one seed; no significance/generalization claim')
    (out/'RESULTS.json').write_text(json.dumps(dict(results=rows,decision=decision),indent=2)+'\n')
    fig,ax=plt.subplots(1,2,figsize=(11,4.5));gp=truth[:,:3,3];dims=np.argsort(np.var(gp,axis=0))[-2:]
    ax[0].plot(gp[:,dims[0]],gp[:,dims[1]],'k--',label='GT')
    for arm,arr in arrays.items():
        p=arr['aligned_positions'];ax[0].plot(p[:,dims[0]],p[:,dims[1]],label=arm)
        ax[1].plot(ids,arr['position_errors'],label=arm)
    ax[0].set(title='One global Sim3 fit per complete trajectory',xlabel=f'Axis {dims[0]} (game units)',ylabel=f'Axis {dims[1]} (game units)');ax[0].axis('equal')
    ax[1].set(title='Offline pose error',xlabel='Original RGB frame ID',ylabel='Error (game units)')
    for a in ax:a.grid(alpha=.2);a.legend(fontsize=8)
    fig.suptitle('Local RTX5060: MP-SfM-style Cauchy depth-prior transfer');fig.tight_layout()
    fig.savefig(out/'FOUR_ARM_TRAJECTORIES.png',dpi=160);fig.savefig(out/'FOUR_ARM_TRAJECTORIES.pdf');plt.close(fig)
    fig,ax=plt.subplots(1,2,figsize=(10,4))
    for arm in ['ROBUST','ROBUST_A5']:
        rs=[r for r in trace_rows if r['arm']==arm]
        for iteration in [1,2]:
            vs=[r['mean_q'] for r in rs if r['iteration']==iteration]
            ax[0].hist(vs,bins=40,histtype='step',label=f'{arm} inner {iteration}')
        calls=sorted(set(r['call'] for r in rs));ax[1].plot(calls,[np.mean([r['mean_q'] for r in rs if r['call']==c]) for c in calls],label=arm)
    ax[0].set(xlabel='Mean IRLS weight per keyframe',ylabel='BA-event count',title='Diagnostic counts are not independent samples')
    ax[1].set(xlabel='BA call',ylabel='Mean IRLS weight',title='Residual-dependent prior attenuation')
    for a in ax:a.legend(fontsize=7);a.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'ROBUST_WEIGHT_DIAGNOSTIC.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(results=rows,decision=decision),indent=2))
if __name__=='__main__':main()
