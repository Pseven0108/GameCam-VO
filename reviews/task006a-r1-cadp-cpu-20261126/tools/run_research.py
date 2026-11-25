"""Execute only synthetic CPU research. Refuses to overwrite a previous attempt."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from dataclasses import asdict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))

if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
    raise RuntimeError('CPU-only: CUDA_VISIBLE_DEVICES must be explicitly empty')

import numpy as np
import scipy
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve
from cadp_cpu import *
from synthetic import make_fixture,large_fixture
from test_cadp import run_suite

ATOL=2e-11
RTOL=2e-11


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path,rows):
    if not rows:
        raise RuntimeError('Empty experiment table')
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,keys); w.writeheader(); w.writerows(rows)


def array_sha(a):
    a=np.ascontiguousarray(a)
    h=hashlib.sha256()
    h.update(json.dumps({'shape':a.shape,'dtype':str(a.dtype)},sort_keys=True).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def errors(actual,expected):
    return {'max_abs_error':float(np.max(np.abs(actual-expected))),
            'max_scaled_error':float(np.max(np.abs(actual-expected)/(ATOL+RTOL*np.abs(expected)))),
            'pass':bool(np.allclose(actual,expected,atol=ATOL,rtol=RTOL))}


def covariance_experiments(out):
    rows=[]; saved={}
    for seed in (43,44,45,1729,2026,20261126):
        for p,n in ((2,7),(6,24),(12,48),(24,96)):
            x=make_fixture(seed,p,n); fac=prior_off(x.geometry)
            full=full_covariance(fac)
            j=joint_precision(fac)
            # Oracle does not use the block inverse expression or its Cholesky.
            direct=np.linalg.solve(j,np.eye(j.shape[0]))[p:,p:]
            sparse=spsolve(csc_matrix(j),csc_matrix(np.eye(j.shape[0]))).toarray()[p:,p:]
            for block in (1,5,16,128):
                diag=blocked_diagonal(fac,block)
                err=errors(diag,np.diag(direct))
                ef=errors(full,direct); es=errors(sparse,direct)
                rows.append({'seed':seed,'npose':p,'ndepth':n,'block':block,
                             **err,'full_max_abs':ef['max_abs_error'],'sparse_max_abs':es['max_abs_error'],
                             'full_pass':ef['pass'],'sparse_pass':es['pass'],
                             'marginal_minus_conditional_min':float(np.min(diag-fac.q)),
                             'Schur_condition':fac.condition,
                             'dense_input_hash':array_sha(j)})
                if not all((err['pass'],ef['pass'],es['pass'])):
                    raise AssertionError(f'Covariance oracle mismatch seed={seed},p={p},n={n},block={block}')
            if p==6 and seed in (43,44,45):
                prefix=f'seed{seed}_'
                for k,v in {'A':x.geometry.A,'E':x.geometry.E,'Cg':x.geometry.Cg,'eta':x.geometry.eta,
                            'full_covariance':full,'joint_precision':j,'disparity':x.disparity,
                            'mono_disparity':x.mono_disparity,'bx':x.bx,'bg':x.bg}.items():
                    saved[prefix+k]=v
    np.savez_compressed(out/'SYNTHETIC_SMALL_INPUTS_AND_ORACLES.npz',**saved)
    write_csv(out/'COVARIANCE_ORACLE_COMPARISON.csv',rows)
    return {'systems':24,'block_comparisons':len(rows),'all_pass':all(r['pass'] for r in rows),
            'max_abs_block_vs_joint_inverse':max(r['max_abs_error'] for r in rows),
            'max_abs_full_vs_joint_inverse':max(r['full_max_abs'] for r in rows),
            'max_abs_sparse_vs_joint_inverse':max(r['sparse_max_abs'] for r in rows)}


def endpoint_experiments(out):
    rows=[]
    for seed in (43,44,45):
        for eta in (0.0001,0.003,0.1):
            x=make_fixture(seed,12,36,eta_scale=eta); g=x.geometry
            off=prior_off(g); covariance_before=blocked_diagonal(off)
            for rho in (0.,0.1,0.5,0.9,1.):
                c,b=cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,rho)
                dx,dz,fac=solve_ba_step(g,x.bx,b,c)
                direct=np.linalg.solve(joint_precision(fac),np.r_[x.bx,b])
                err=errors(np.r_[dx,dz],direct)
                endpoint=rho in (0.,1.)
                exact_c=exact_b=exact_dx=exact_dz=guarded_exact=None
                if endpoint:
                    cn,bn=native_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,bool(rho))
                    dxn,dzn,fn=solve_ba_step(g,x.bx,bn,cn)
                    exact_c=bool(np.array_equal(c,cn)); exact_b=bool(np.array_equal(b,bn))
                    exact_dx=bool(np.array_equal(dx,dxn)); exact_dz=bool(np.array_equal(dz,dzn))
                    guarded=native_guarded_backsub(g.E,fac.q,b,dx)
                    guardedn=native_guarded_backsub(g.E,fn.q,bn,dxn)
                    guarded_exact=bool(np.array_equal(guarded,guardedn))
                    if not all((exact_c,exact_b,exact_dx,exact_dz,guarded_exact)):
                        raise AssertionError('Endpoint not exactly recovered in CPU arithmetic')
                if not err['pass']: raise AssertionError('Joint-system RHS mismatch')
                np.testing.assert_array_equal(covariance_before,blocked_diagonal(prior_off(g)))
                rows.append({'seed':seed,'eta_scale':eta,'rho':rho,'alpha':0.01,
                             'is_endpoint':endpoint,'C_exact':exact_c,'b_exact':exact_b,
                             'dx_CPU_exact':exact_dx,'dz_CPU_exact':exact_dz,
                             'native_ix_guard_dz_CPU_exact':guarded_exact,
                             **err,'dx_norm':float(np.linalg.norm(dx)),
                             'dz_norm':float(np.linalg.norm(dz)),
                             'C_min':float(c.min()),'post_Schur_condition':fac.condition,
                             'prior_off_covariance_unchanged':True,
                             'scope':'CPU mathematical joint-system; NOT native CUDA backsub'})
    write_csv(out/'ENDPOINT_AND_CONTINUOUS_RHO_COMPARISON.csv',rows)
    return {'rho_configurations':len(rows),'endpoint_configurations':sum(r['is_endpoint'] for r in rows),
            'all_CPU_endpoints_exact':True,'joint_solve_all_pass':all(r['pass'] for r in rows),
            'GPU_equivalence_tested':False}


def uncertainty_experiments(out):
    rows=[]; parameter_rows=[]
    for seed in (43,44,45):
        for scale in (1e-4,1e-2,1.,1e2,1e4):
            x=make_fixture(seed,6,60,geometry_scale=scale); g=x.geometry
            v=blocked_diagonal(prior_off(g))
            stats=frame_statistics(v,x.disparity,x.frame_ids,x.observation_count,g.Cg,k=2,tau=2)
            for stat in stats:
                rows.append({'seed':seed,'geometric_information_scale':scale,**asdict(stat),
                             'k_demo_only':2.,'tau_demo_only':2.,'epsilon':1e-6,
                             'prior_in_covariance':False})
            if seed==43 and scale==1:
                for k in (0.1,1.,10.):
                    for tau in (0.1,1.,2.,10.):
                        s=frame_statistics(v,x.disparity,x.frame_ids,x.observation_count,g.Cg,k=k,tau=tau)
                        for st in s:
                            parameter_rows.append({'k':k,'tau':tau,**asdict(st),'calibrated':False})
    write_csv(out/'GEOMETRY_TO_FRAME_RHO.csv',rows)
    write_csv(out/'UNCALIBRATED_SIGMOID_SENSITIVITY.csv',parameter_rows)
    decreasing=[]
    for seed in (43,44,45):
        for fid in range(3):
            group=[r for r in rows if r['seed']==seed and r['frame_id']==fid]
            u=np.array([r['uncertainty'] for r in group])
            decreasing.append(bool(np.all(np.diff(u)<0)))
    if not all(decreasing): raise AssertionError('Fixture did not exhibit expected information ordering')
    # Include deliberately observed but completely uninformative pixels.
    masking=frame_statistics(np.array([1.,1.,1e8,1e8,1e8,1.]),np.array([1.,1.,1.,1.,1.,np.nan]),
               np.zeros(6,dtype=int),np.ones(6,dtype=int),np.array([1.,1.,0.,0.,0.,0.]),k=2,tau=2)
    write_json(out/'MASK_AND_MEDIAN_COUNTEREXAMPLE.json',{
        'all_observed_weak_pixels_retained':asdict(masking[0]),
        'incorrect_Cg_positive_only_median':1/(1+1e-6),
        'conclusion':'Filtering by Cg>0 can hide a majority of weak observations; missing support must be reported',
        'median_convention':'midpoint average on even sample count; differs from Torch lower median'})
    return {'frame_records':len(rows),'sensitivity_records':len(parameter_rows),
            'geometry_ordering_checks':len(decreasing),'all_ordering_pass':all(decreasing),
            'k_tau_calibrated':False,'proves_Metric3D_accuracy':False}


def stability_experiments(out):
    rows=[]
    # Each specification has an expected accept/reject outcome fixed before execution.
    cases=[
      ('gauge_without_damping',np.zeros((2,2)),np.zeros((2,1)),np.ones(1),0.,0.,'REJECT'),
      ('gauge_with_native_ep',np.zeros((2,2)),np.zeros((2,1)),np.ones(1),1e-4,0.1,'ACCEPT'),
      ('condition_1e10',np.diag([1.,1e-10]),np.zeros((2,1)),np.ones(1),0.,0.,'ACCEPT'),
      ('condition_1e14',np.diag([1.,1e-14]),np.zeros((2,1)),np.ones(1),0.,0.,'REJECT'),
      ('condition_regularized',np.diag([1.,1e-14]),np.zeros((2,1)),np.ones(1),1e-4,0.1,'ACCEPT'),
      ('indefinite_schur',np.eye(2),np.ones((2,1))*10,np.ones(1),1e-4,0.1,'REJECT'),
      ('zero_depth_C',np.eye(2),np.zeros((2,1)),np.zeros(1),1e-4,0.1,'REJECT'),
      ('negative_depth_C',np.eye(2),np.zeros((2,1)),-np.ones(1),1e-4,0.1,'REJECT'),
      ('NaN_in_E',np.eye(2),np.array([[np.nan],[0.]]),np.ones(1),1e-4,0.1,'REJECT'),
      ('Inf_in_A',np.diag([1.,np.inf]),np.zeros((2,1)),np.ones(1),1e-4,0.1,'REJECT'),
      ('tiny_positive_C',np.eye(2),np.zeros((2,1)),np.array([1e-200]),1e-4,0.1,'ACCEPT'),
      ('reciprocal_overflow_C',np.eye(2),np.zeros((2,1)),np.array([1e-320]),1e-4,0.1,'REJECT')]
    for name,a,e,c,lm,ep,expected in cases:
        try:
            fac=factor_schur(a,e,c,lm,ep)
            actual='ACCEPT'; reason='finite SPD factor'; cond=fac.condition
        except (DomainError,NumericalError) as exc:
            actual='REJECT'; reason=str(exc); cond=None
        rows.append({'case':name,'expected':expected,'actual':actual,'pass':actual==expected,
                     'reason':reason,'condition':cond,'lm':lm,'ep':ep,'max_condition_policy':1e12})
        if actual!=expected: raise AssertionError(f'Stability outcome {name}')
    # Eta controls the regularized answer even when geometry contains no information.
    for eta in (1e-9,1e-6,1e-3,1e-1,1e2):
        g=Geometry(np.zeros((2,2)),np.zeros((2,9)),np.zeros(9),np.ones(9)*eta)
        fac=prior_off(g); v=blocked_diagonal(fac)
        s=frame_statistics(v,np.ones(9),np.zeros(9,dtype=int),np.ones(9,dtype=int),g.Cg,k=2,tau=2)[0]
        rows.append({'case':'zero_geometry_eta_sensitivity','expected':'ACCEPT','actual':'ACCEPT','pass':True,
                     'eta':eta,'median_variance':float(np.median(v)),**asdict(s),
                     'reason':'regularizer-dominated finite uncertainty, not observed metric certainty'})
    write_csv(out/'NUMERICAL_STABILITY_CASES.csv',rows)
    return {'cases':len(rows),'all_expected_outcomes':all(r['pass'] for r in rows),
            'no_jitter':True,'no_pseudoinverse':True,'condition_limit_is_prototype_policy':True}


def inaccurate_prior_counterexample(out):
    # Two weighted linear residuals, Jp=[1,1], Jd=[1,2], weight=.001.
    # Ground-truth LOCAL increments dx=.2, dz=-.2; initial disparity=1.
    # This is a synthetic least-squares counterexample, no camera GT is read.
    g=Geometry(np.array([[0.002]]),np.array([[0.003]]),np.array([0.005]),np.array([0.001]))
    off=prior_off(g)
    v=blocked_diagonal(off)
    stats=frame_statistics(v,np.ones(1),np.array([0]),np.array([2]),g.Cg,k=2,tau=2)
    adaptive=stats[0].rho
    rows=[]
    for accuracy,dm in [('accurate_prior',0.8),('inaccurate_prior',8.0)]:
        for label,rho in [('D0',0.),('adaptive_demo',adaptive),('D1',1.)]:
            c,b=cadp_depth_terms(g.Cg,np.array([-0.0004]),g.eta,np.ones(1),np.array([dm]),rho)
            dx,dz,_=solve_ba_step(g,np.array([-0.0002]),b,c)
            rows.append({'prior':accuracy,'method':label,'mono_disparity':dm,'u':stats[0].uncertainty,
                         'rho':rho,'dx':float(dx[0]),'dz':float(dz[0]),
                         'pose_increment_absolute_error':abs(float(dx[0])-0.2),
                         'depth_increment_absolute_error':abs(float(dz[0])+0.2),
                         'scope':'analytic synthetic local normal equation, not SLAM trajectory'})
    bad0=next(r for r in rows if r['prior']=='inaccurate_prior' and r['method']=='D0')
    badr=next(r for r in rows if r['prior']=='inaccurate_prior' and r['method']=='adaptive_demo')
    if badr['pose_increment_absolute_error']<=bad0['pose_increment_absolute_error']:
        raise AssertionError('Counterexample did not show the pre-specified adverse-prior effect')
    write_csv(out/'INACCURATE_PRIOR_COUNTEREXAMPLE.csv',rows)
    return {'rows':len(rows),'high_rho_same_for_good_and_bad_prior':True,
            'adverse_prior_pose_error_D0':bad0['pose_increment_absolute_error'],
            'adverse_prior_pose_error_adaptive_demo':badr['pose_increment_absolute_error'],
            'universal_improvement_claim_falsified_on_synthetic_system':True,
            'VIPER_CADP_efficacy_evaluated':False}


def adaptive_pipeline_experiments(out):
    rows=[]
    for seed in (43,44,45):
        for scale in (1e-2,1.,100.):
            x=make_fixture(seed,12,36,geometry_scale=scale)
            plan=build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,x.observation_count,k=2,tau=2,block_size=5)
            c,b=cadp_depth_terms(x.geometry.Cg,x.bg,x.geometry.eta,x.disparity,x.mono_disparity,plan.pixel_rho)
            dx,dz,fac=solve_ba_step(x.geometry,x.bx,b,c)
            direct=np.linalg.solve(joint_precision(fac),np.r_[x.bx,b])
            err=errors(np.r_[dx,dz],direct)
            if not err['pass']: raise AssertionError('Adaptive pipeline joint solve mismatch')
            rows.append({'seed':seed,'geometry_scale':scale,'rho_min':float(plan.pixel_rho.min()),
                         'rho_max':float(plan.pixel_rho.max()),'rho_writeable':plan.pixel_rho.flags.writeable,
                         'dx_norm':float(np.linalg.norm(dx)),'dz_norm':float(np.linalg.norm(dz)),**err,
                         'scope':'synthetic first-linearization plan; no native-U iteration integration'})
    write_csv(out/'ADAPTIVE_PIPELINE_COMPARISON.csv',rows)
    return {'cases':len(rows),'all_pass':all(r['pass'] for r in rows),'rho_frozen_readonly':True}


def block_scale_experiments(out):
    start=time.perf_counter()
    g,d,frame_ids=large_fixture()
    construct=time.perf_counter()-start
    start=time.perf_counter(); fac=prior_off(g); factor_seconds=time.perf_counter()-start
    # Independent diagonal oracle uses H^-1 solves instead of column norms.
    eq=g.E*fac.q
    reference=fac.q+np.einsum('ij,ij->j',eq,fac.solve_pose(eq))
    rows=[]
    for block in (64,256,1024,4096):
        start=time.perf_counter(); diag=blocked_diagonal(fac,block); elapsed=time.perf_counter()-start
        err=errors(diag,reference)
        if not err['pass']: raise AssertionError('Dimension-matched synthetic block mismatch')
        rows.append({'seed':20261126,'npose':72,'ndepth':54000,'block':block,**err,
                     'seconds_single_CPU_run':elapsed,
                     'two_block_buffers_bytes':2*72*min(block,54000)*8,
                     'E_bytes':g.E.nbytes,'diag_output_bytes':diag.nbytes,
                     'full_covariance_not_allocated':True,'real_R3_data':False})
    stats=frame_statistics(diag,d,frame_ids,np.ones(54000,dtype=int),g.Cg,k=2,tau=2)
    write_csv(out/'DIMENSION_MATCHED_SYNTHETIC_BLOCKS.csv',rows)
    write_csv(out/'DIMENSION_MATCHED_SYNTHETIC_FRAME_STATS.csv',[asdict(s) for s in stats])
    write_json(out/'DIMENSION_MATCHED_INPUT_RECEIPT.json',{
        'generator':'synthetic.large_fixture','seed':20261126,'shape':[72,54000],
        'scope':'Generated synthetic Gram system, NOT R3 E reconstruction',
        'array_sha256':{name:array_sha(value) for name,value in
                         {'A':g.A,'E':g.E,'Cg':g.Cg,'eta':g.eta,'d':d,'frame_ids':frame_ids}.items()},
        'construction_seconds':construct,'factor_seconds':factor_seconds,
        'float64_full_covariance_bytes_avoided':54000*54000*8,
        'memory_metrics':'Array sizes and workspace arithmetic; not measured process peak/RSS/GPU memory'})
    return {'block_comparisons':len(rows),'all_pass':all(r['pass'] for r in rows),
            'max_abs_error':max(r['max_abs_error'] for r in rows),
            'CPU_seconds_by_block':{str(r['block']):r['seconds_single_CPU_run'] for r in rows},
            'real_time_integration_tested':False,'online_overhead_tested':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    out=Path(args.out).resolve()
    if ROOT not in out.parents: raise RuntimeError('Output must be inside this independent R1 directory')
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    write_json(out/'RUN_START.json',{'argv':sys.argv,'python':sys.executable,'numpy':np.__version__,
        'scipy':scipy.__version__,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],
        'ATOL':ATOL,'RTOL':RTOL,'seed_list':[43,44,45,1729,2026,20261126],
        'no_inputs_from_VIPER_R3_or_C0':True})
    try:
        units=run_suite(out)
        if not units['success']: raise AssertionError('CPU unit tests failed')
        summary={'unit_tests':{k:units[k] for k in ('tests_run','passed','failures','errors','success','torch_imported')}}
        for name,fn in [('covariance',covariance_experiments),('endpoints',endpoint_experiments),
                        ('uncertainty',uncertainty_experiments),('stability',stability_experiments),
                        ('inaccurate_prior_counterexample',inaccurate_prior_counterexample),
                        ('adaptive_pipeline',adaptive_pipeline_experiments),
                        ('dimension_matched_blocks',block_scale_experiments)]:
            print('Running',name,flush=True)
            summary[name]=fn(out)
        summary['success']=True
        summary['elapsed_seconds']=time.perf_counter()-started
        summary['torch_imported']='torch' in sys.modules
        summary['model_imported']=any(k.startswith(('torch','cv2','transformers','safetensors')) for k in sys.modules)
        write_json(out/'RESEARCH_RESULTS.json',summary)
        print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
        code=0
    except Exception:
        (out/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8')
        traceback.print_exc()
        code=1
    write_json(out/'RUN_EXIT.json',{'exit_code':code,'elapsed_seconds':time.perf_counter()-started,
              'torch_imported':'torch' in sys.modules})
    return code


if __name__=='__main__':
    sys.exit(main())
