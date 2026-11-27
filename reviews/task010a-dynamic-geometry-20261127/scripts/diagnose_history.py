"""Recalculate TASK009 gates on sealed BA correspondences, not proxy coordinates."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import csv
import json
import sys
from pathlib import Path
import numpy as np
import torch
from scipy.stats import spearmanr

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from gamecam.modules.dynamic_prior.dynamic_mask import GateConfig,DynamicObservationGate,sample_probability
from gamecam.modules.dynamic_prior.feature_alignment import ImageGeometry
OLD=Path('D:/aaa/GameCam-VO-TASK009/experiments/TASK009/outputs')
PI3=Path('D:/aaa/GameCam-VO/experiments/task008_pi3mos/retrieved/outputs/night007/A/predictions')
OUT=ROOT/'experiments/TASK010-A/01_failure_diagnosis'


def summary(a):
    a=np.asarray(a)
    return {'min':float(a.min()),'p50':float(np.median(a)),'p90':float(np.quantile(a,.9)),
            'p99':float(np.quantile(a,.99)),'max':float(a.max()),'mean':float(a.mean())}


def main():
    torch.set_num_threads(2)
    probs={}
    for fid in range(301,333):
        with np.load(PI3/f'{fid:05d}.npz',allow_pickle=False) as z:
            assert int(z['target_rgb_id'])==fid
            probs[fid]=torch.from_numpy(z['dynamic_probability_model'].copy())
    records=[];pairs=[]
    for run in sorted(OLD.glob('droid_E*')):
        if not (run/'dynamic_gate.jsonl').exists():continue
        receipt=json.loads((run/'receipt.json').read_text())
        conf=receipt.get('gate_config')
        if conf is None:
            # The sealed TASK009 report explicitly distinguishes default/weak runs.
            conf={'alpha':.5,'beta':.5,'floor':.5} if 'weak' in run.name else {'alpha':1.,'beta':1.,'floor':.1}
        gate=DynamicObservationGate(GateConfig(alpha=conf['alpha'],beta=conf['beta'],min_gate=conf['floor']))
        calls=[json.loads(x) for x in (run/'dynamic_gate.jsonl').read_text().splitlines()]
        records.append({'run':run.name,'calls':len(calls),'alpha':conf['alpha'],'beta':conf['beta'],
            'min_gate':conf['floor'],'call_weighted_gate_mean':float(np.average([c['gate_mean'] for c in calls],weights=[c['shape'][1] for c in calls])),
            'min_attenuated_fraction':min(c['attenuated_fraction'] for c in calls),
            'max_attenuated_fraction':max(c['attenuated_fraction'] for c in calls),
            'first_gate_mean':calls[0]['gate_mean'],'first_attenuated_fraction':calls[0]['attenuated_fraction']})
        for path in sorted((run/'native_ba_observations').glob('*.npz')):
            with np.load(path,allow_pickle=False) as z:
                i,j=int(z['source_rgb']),int(z['target_rgb'])
                target=torch.from_numpy(z['target'].copy())[None]
                u=z['source_u'].copy()
                h,w=target.shape[1:3]
                yy,xx=torch.meshgrid(torch.arange(h),torch.arange(w),indexing='ij')
                src=torch.stack((xx,yy),-1).float()[None]
                geom=ImageGeometry((216,384),tuple(probs[i].shape))
                mi,_=sample_probability(probs[i][None],geom.feature_to_map(src))
                mj,_=sample_probability(probs[j][None],geom.feature_to_map(target))
                ones=torch.ones(1,1,h,w,2)
                g,stats=gate(ones,probs[i][None],probs[j][None],geom.feature_to_map(src),geom.feature_to_map(target))
                g=g[0,0,:,:,0].numpy()
                # Native source-end CUDA formula; target-end U was NOT saved.
                native=np.clip(1/np.maximum(45*u-35,.1),0,1)
                corr=spearmanr(mi.numpy().ravel(),u.ravel()).statistic
                pairs.append({'run':run.name,'snapshot':path.name,'source_rgb':i,'target_rgb':j,
                    'gate':summary(g),'source_U':summary(u),'native_source_UBA_weight':summary(native),
                    'effective_source_gate_times_UBA':summary(g*native),
                    'probability_source':summary(mi.numpy()),'probability_target':summary(mj.numpy()),
                    'spearman_M_U':float(corr) if np.isfinite(corr) else None,
                    'both_attenuate_fraction':float(np.mean((g<.999999)&(native<.999999))),
                    'gate_static_score_below_point1_fraction':float(np.mean(g[mi[0].numpy()<=.1]<.999999)),
                    'target_U_saved':False,'causal_attribution':'NOT_ESTABLISHED'})
    result={'all_probabilities':summary(torch.stack(list(probs.values())).numpy()),'gate_calls':records,
            'matched_snapshot_recalculation':pairs,'CUDA_initialized':torch.cuda.is_initialized(),
            'limits':'Source U only. These are same-state weight algebra diagnostics, not a counterfactual trajectory result.'}
    (OUT/'HISTORICAL_GATE_RECALCULATION.json').write_text(json.dumps(result,indent=2))
    fields=list(records[0])
    with (OUT/'TASK009_GATE_CALL_SUMMARY.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    print(json.dumps({'gate_call_summaries':records,'matched_snapshots':len(pairs),'cuda_initialized':torch.cuda.is_initialized()},indent=2))


if __name__=='__main__':main()
