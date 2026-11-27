"""Confirm ordering-only correction did not change any experimental result."""
from common import *

def main():
    a=TASK/'runs/cpu_001';b=TASK/'runs/cpu_002';tables=[];arrays=[]
    names=['metrics_per_frame.csv','metrics_summary.csv','fusion_comparison.csv','risk_coverage.csv','risk_error_bins.csv','probability_metrics.csv','probability_reliability_bins.csv','regression_metrics.csv','signal_complementarity.csv','viper_signal_statistics.csv','viper_raw_signal_statistics.csv','historical_reproduction.csv','depth_error_context.csv','CALIBRATION_MODELS.json']
    for name in names:
        same=(a/name).read_bytes()==(b/name).read_bytes();tables.append({'file':name,'identical_bytes':same,'sha256':sha(b/name)})
        if not same:raise RuntimeError('Unexpected CPU flow recheck output change: '+name)
    for p in sorted((a/'risk_maps').glob('*.npz')):
        other=b/'risk_maps'/p.name
        with np.load(p,allow_pickle=False) as x,np.load(other,allow_pickle=False) as y:
            for k in x.files:
                same=x[k].tobytes()==y[k].tobytes();arrays.append({'sample':p.stem,'field':k,'bitwise_identical':same})
                if not same:raise RuntimeError('Unexpected array recheck difference')
    dump(b/'CPU_FLOW_RECHECK.json',{'status':'PASS','reason':'First pass rank function never used GT, but loader opened GT before calling it. Corrected the call order to literally compute full-image ranks before GT loading, as frozen protocol states. No metric, fusion weight, mask, fitting split or signal formula changed.','first_pass':'cpu_001','final_pass':'cpu_002','independent_experimental_repetitions':False,'new_GPU_inference':0,'identical_result_tables':tables,'bitwise_array_checks':arrays})
    # Reuse figures only because all source tables and array contents match.
    p=TASK/'figures/FIGURE_SOURCE_INDEX.json';index=json.loads(p.read_text())
    for r in index:
        r['score_maps_sha256']=sha(b/'risk_maps'/(r['sample_id']+'.npz'));r['rendered_source_values_identical_to_final_run']=True
    dump(p,index)
    print('CPU_FLOW_RECHECK_PASS',len(tables),'identical result files',len(arrays),'bitwise tensor checks')

if __name__=='__main__':main()
