"""Recheck the full artifact without RGB, EXR, model weights, Torch or a GPU.

Usage after extracting the complete review:
python code/replay_from_arrays.py --artifact-root .
"""
import argparse,ast,csv,json,sys
from pathlib import Path
import numpy as np
from scipy.special import expit
from scipy.stats import spearmanr

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifact-root',type=Path,required=True);parser.add_argument('--output',type=Path);a=parser.parse_args();root=a.artifact_root.resolve()
    sys.path.insert(0,str(root/'code'));sys.path.insert(0,str(root/'intake/legacy_code'))
    from fusion_math import scores,probability_metrics,error_metrics
    from reliability_metrics import binary_ranking
    tree=ast.parse((root/'intake/legacy_code/evaluate_pilot.py').read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fast_rc')
    namespace={'np':np};exec(compile(ast.Module(body=[function],type_ignores=[]),'<frozen fast_rc>','exec'),namespace);risk_coverage=namespace['fast_rc']
    def rows(name):
        with (root/'results'/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
    expected={(r['sample_id'],r['view'],r['method']):r for r in rows('metrics_per_frame.csv')}
    probabilities={(r['sample_id'],r['view'],r['method']):r for r in rows('probability_metrics.csv')}
    regression={(r['sample_id'],r['view'],r['method']):r for r in rows('regression_metrics.csv')}
    models={(r['view'],r['method']):r for r in json.loads((root/'results/CALIBRATION_MODELS.json').read_text())['models']}
    views=['FROZEN_BICUBIC_ZERO_EXTENDED','R2_2_BILINEAR_SAME_FOCAL'];checks=[];map_checks=0
    for path in sorted((root/'results/minimal_replay_inputs').glob('*.npz')):
        sid=path.stem
        with np.load(path,allow_pickle=False) as z,np.load(root/'results/risk_maps'/(sid+'.npz'),allow_pickle=False) as stored:
            for view in views:
                if sid.startswith('VIPER') and view!=views[0]:continue
                conf=z['native_confidence'].astype(float)
                p=z['native_depth'].astype(float) if view==views[0] else z['native_bilinear_same_focal'].astype(float)
                flip=z['flip_depth'][:,::-1].astype(float) if view==views[0] else z['flip_bilinear_same_focal'][:,::-1].astype(float)
                signal=np.abs(p-flip)/(np.abs(p)+1e-6);methods,n,f=scores(conf,signal)
                if view==views[0]:
                    for key,value in [('rank_native',n),('rank_flip',f),('risk_fusion',methods['RankFusion']),('risk_max',methods['MaxFusion'])]:
                        np.testing.assert_array_equal(value,stored[key]);map_checks+=1
                if not sid.startswith('MVS'):continue
                valid=stored['valid_GT'];error=(stored['AbsRel'] if view==views[0] else z['AbsRel_sensitivity'])[valid]
                for method,riskmap in methods.items():
                    risk=riskmap[valid];rank=binary_ranking(error>.2,risk);rc=risk_coverage(error,risk)
                    got={'AUROC':rank['AUROC'],'AP':rank['AUPRC'],'AUSE':rc['AUSE'],'Spearman':float(spearmanr(error,risk).statistic)}
                    prior=expected[sid,view,method]
                    for key,value in got.items():
                        diff=abs(value-float(prior[key]));checks.append(diff)
                        if diff>1e-12:raise RuntimeError('Artifact ranking replay mismatch')
                    if '_0001_' not in sid:continue
                    m=models[view,method];model=m['probability'];v=model['slope']*(risk-model['mean'])/model['sd']+model['intercept'];pr=expit(v)
                    ps,_=probability_metrics(pr,v,error>.2);prior=probabilities[sid,view,method]
                    for key in ['Brier','NLL','ECE10']:
                        diff=abs(ps[key]-float(prior[key]));checks.append(diff)
                        if diff>1e-12:raise RuntimeError('Artifact probability replay mismatch')
                    model=m['AbsRel_regression'];estimated=np.interp(risk,model['x_thresholds'],model['y_thresholds']);reg=error_metrics(estimated,error);prior=regression[sid,view,method]
                    for key,value in reg.items():
                        diff=abs(value-float(prior[key]));checks.append(diff)
                        if diff>1e-12:raise RuntimeError('Artifact regression replay mismatch')
    result={'status':'PASS','bitwise_risk_map_comparisons':map_checks,'scalar_metric_comparisons':len(checks),'maximum_absolute_difference':float(max(checks)),'atol':1e-12,'raw_GT_RGB_models_or_OpenEXR_needed':False,'new_probability_or_regression_fits':0,'Torch_imported':'torch' in sys.modules}
    if result['Torch_imported']:raise RuntimeError('Unexpected PyTorch import')
    if a.output:a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
