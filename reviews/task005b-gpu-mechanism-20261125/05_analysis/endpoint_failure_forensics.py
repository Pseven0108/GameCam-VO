"""CPU-only exact adjudication of the saved, failed native endpoint pair."""
import pathlib,tarfile,io,json,csv
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')

def load(archive,name):
    with np.load(io.BytesIO(archive.extractfile('./'+name).read()),allow_pickle=False) as data:return {k:data[k] for k in data.files}

def main():
    path=RECEIVER/'partial_D0_S1_RGB233.tar'
    with tarfile.open(path,'r:') as archive:
        failure=json.load(archive.extractfile('./ENDPOINT_FAILURE.json'))
        candidate=load(archive,'NATIVE_UPDATE_D_FAILED_ENDPOINT.npz')
        original=load(archive,'NATIVE_UPDATE_D0_ORIGINAL.npz')
        frozen=load(archive,'FROZEN_D.npz')
        receipts=[m.name for m in archive if m.name.endswith('.receipt.json')]
    rows=[];violations=[]
    fields=[(n,'final_'+n) for n in ('poses','disps','uncertainties','temp_y_cdot','affine_weights')]+[('dx_last','last_dx'),('dz_last','last_dz')]
    for name,key in fields:
        actual=candidate[key];reference=original[name]
        delta=np.abs(actual.astype(np.float64)-reference.astype(np.float64))
        tolerance=1e-6+1e-5*np.abs(reference.astype(np.float64))
        # The runtime uses NumPy's native dtype isclose operation. Preserve its
        # boolean result; float64 deltas are only explanatory diagnostics.
        failed=~np.isclose(actual,reference,atol=1e-6,rtol=1e-5,equal_nan=False)
        worst=np.unravel_index(np.argmax(delta/tolerance),actual.shape)
        rows.append({'field':name,'elements':int(actual.size),'violations':int(failed.sum()),'max_absolute_difference':float(delta.max()),
                     'max_error_to_allowed_tolerance':float((delta/tolerance).max()),'worst_index':list(worst),
                     'worst_candidate':float(actual[worst]),'worst_original':float(reference[worst]),
                     'worst_absolute_difference':float(delta[worst]),'worst_allowed_tolerance':float(tolerance[worst]),
                     'runtime_allclose_reproduced':bool(np.allclose(actual,reference,atol=1e-6,rtol=1e-5,equal_nan=False))})
        for index in np.argwhere(failed):
            slot=tuple(index)
            violations.append({'field':name,'index':json.dumps(index.tolist()),'candidate':float(actual[slot]),'original':float(reference[slot]),
                               'absolute_difference':float(delta[slot]),'allowed_tolerance':float(tolerance[slot]),'ratio':float(delta[slot]/tolerance[slot])})
    first_delta=float(np.max(np.abs(candidate['iter1_dx']-frozen['iter1_dx'])))
    candidate_calls=sum(not name.endswith('_ORIGINAL.receipt.json') for name in receipts)+1
    original_calls=sum(name.endswith('_ORIGINAL.receipt.json') for name in receipts)
    report={'state':'D0_S1_RGB233','tag':failure['tag'],'failure_reproduced_on_CPU':any(not row['runtime_allclose_reproduced'] for row in rows),
            'atol':1e-6,'rtol':1e-5,'fields':rows,'total_elements':sum(r['elements'] for r in rows),'total_violations':sum(r['violations'] for r in rows),
            'candidate_first_iteration_dx_equals_own_frozen_D':first_delta==0,'candidate_first_iteration_dx_difference_max':first_delta,
            'all_saved_arrays_finite':all(np.isfinite(a).all() for group in (candidate,original) for a in group.values()),
            'partial_original_calls':original_calls,'partial_candidate_calls_including_failed_endpoint':candidate_calls,
            'partial_total_native_calls':candidate_calls+original_calls,'GPU_replays_for_forensics':0,
            'cause':'NOT_ESTABLISHED','floating_point_or_U_affine_feedback_hypothesis':'PLAUSIBLE_NOT_PROVEN',
            'next_minimal_GPU_request_not_executed':'Repeat installed-original versus itself from the identical saved state, and compare candidate, to estimate native stochastic numerical variability before changing tolerances or code.'}
    assert report['failure_reproduced_on_CPU'] and original_calls==4 and candidate_calls==6
    dest=ROOT/'05_analysis/ENDPOINT_FAILURE_FORENSICS.json';dest.write_text(json.dumps(report,indent=2,default=lambda x:int(x) if isinstance(x,np.integer) else bool(x) if isinstance(x,np.bool_) else str(x)))
    with (ROOT/'05_analysis/ENDPOINT_TOLERANCE_VIOLATIONS.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(violations[0]));writer.writeheader();writer.writerows(violations)
    print(json.dumps(report,default=lambda x:int(x) if isinstance(x,np.integer) else bool(x) if isinstance(x,np.bool_) else str(x)))

if __name__=='__main__':main()
