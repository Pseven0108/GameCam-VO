"""Preserve the initial float64-vs-float32 interpolation discrepancy, no GT selection."""
from common import *
def main():
    cpu_only();rows=[]
    for r in records():
        sid=r['sample']['sample_id']
        with np.load(r['local_npz'],allow_pickle=False) as a,np.load(ROOT/'02_restoration/torch_CPU'/(sid+'.npz'),allow_pickle=False) as b:
            for mode in ['native','flip']:
                mine=restore_bilinear(a[mode+'_canonical_depth'],r)*r['sample']['fx']/1000.
                t=b[mode+'_bilinear_same_focal_unclipped'];d=np.abs(mine-t)
                y,x=np.unravel_index(d.argmax(),d.shape)
                rows.append({'sample':sid,'mode':mode,'dtype_torch':str(t.dtype),'max_abs':float(d.max()),'mean_abs':float(d.mean()),
                    'max_rel':float((d/np.maximum(np.abs(t),1e-20)).max()),'failure_count_rtol3e5_atol3e4':int((d>3e-4+3e-5*np.abs(t)).sum()),
                    'y_max_abs':int(y),'x_max_abs':int(x),'mine_at_max':float(mine[y,x]),'torch_at_max':float(t[y,x])})
    dump(ROOT/'02_restoration/INITIAL_FLOAT64_VS_FLOAT32_VALIDATION_FAILURE.json',{'comparisons':rows,'original_criteria_pass':not any(r['failure_count_rtol3e5_atol3e4'] for r in rows),
        'comparison_is_numeric_not_GT_accuracy':True,'standards_not_relaxed':True})
    print(json.dumps(rows[:3],indent=2));print('MAX_ABS',max(x['max_abs'] for x in rows),'TOTAL_EXCEED',sum(x['failure_count_rtol3e5_atol3e4'] for x in rows))
if __name__=='__main__':main()
