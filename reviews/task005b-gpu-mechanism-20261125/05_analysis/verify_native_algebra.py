"""Independent CPU verification of recorded native Schur and depth updates.

No model imports, no CUDA, no native replays. Float64 sums deliberately do not
claim bitwise equivalence to float32 CUDA reductions.
"""
import pathlib, io, tarfile, json, csv, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
RECEIVER = pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')

def compare(actual, expected):
    actual=np.asarray(actual,dtype=np.float64)
    expected=np.asarray(expected,dtype=np.float64)
    delta=actual-expected
    return {'max_abs':float(np.max(np.abs(delta))) if delta.size else 0.,
            'relative_frobenius':float(np.linalg.norm(delta)/max(np.linalg.norm(expected),1e-30)),
            'allclose_1e_5_1e_6':bool(np.allclose(actual,expected,rtol=1e-5,atol=1e-6))}

def indices(inputs, scalars):
    ts=np.arange(scalars['t0'],scalars['t1'])
    source=np.concatenate([ts,inputs['ii']])
    target=np.concatenate([ts,inputs['jj']])
    kx=np.unique(source)
    return source,target,kx

def schur_from_cross_blocks(E,Q,w,source,target,kx,t0,t1):
    """Aggregate duplicate (depth,pose) blocks before the CPU Schur product."""
    P=t1-t0
    S=np.zeros((P*6,P*6),dtype=np.float64)
    sb=np.zeros(P*6,dtype=np.float64)
    for depth_index,depth_slot in enumerate(kx):
        edge_index=np.flatnonzero((source==depth_slot)&(target>=t0)&(target<t1))
        if not len(edge_index):continue
        poses=np.unique(target[edge_index]-t0)
        location={int(p):i for i,p in enumerate(poses)}
        block=np.zeros((len(poses),6,E.shape[-1]),dtype=np.float64)
        for e in edge_index:
            block[location[int(target[e]-t0)]]+=E[e]
        block=block.reshape(-1,E.shape[-1])
        idx=(poses[:,None]*6+np.arange(6)).reshape(-1)
        S[np.ix_(idx,idx)]+=(block*Q[depth_index])@block.T
        sb[idx]+=block@(Q[depth_index]*w[depth_index])
    return S,sb

def native_depth_coupling(E,dx,source,target,kx,t0):
    """Reproduce the native EvT kernel's strict idx > 0 guard, without fixing it."""
    result=np.zeros((len(kx),E.shape[-1]),dtype=np.float64)
    rows={int(k):i for i,k in enumerate(kx)}
    for e,(depth_slot,pose_slot) in enumerate(zip(source,target)):
        pose_index=int(pose_slot-t0)
        if 0<pose_index<len(dx):
            result[rows[int(depth_slot)]]+=np.asarray(dx[pose_index],dtype=np.float64)@E[e]
    return result

def read_common(archive):
    with np.load(io.BytesIO(archive.extractfile('./COMMON_INPUTS.npz').read()),allow_pickle=False) as data:
        inputs={k:data[k] for k in data.files}
    identity=json.load(archive.extractfile('./INPUT_IDENTITY.json'))
    return inputs,identity

def verify(path):
    formulas=[];systems=[];gates=[]
    with tarfile.open(path,'r:') as archive:
        inputs,identity=read_common(archive)
        sc=identity['scalars'];meta=identity['provenance']
        base={k:meta[k] for k in ('arm','D_origin','schedule','rgb')}
        source,target,kx=indices(inputs,sc)
        boundary={'targets_equal_t1':int(np.sum(target==sc['t1'])),
                  'native_EvT_omits_first_active_pose':bool(np.any(target==sc['t0'])),
                  'first_active_pose_index':sc['t0'],
                  'first_active_pose_RGB':identity['slot_rgb_tokens'][sc['t0']]}
        alpha=np.float32(sc['gamma_depth'])
        mono=inputs['mono'][kx].reshape(len(kx),-1)
        mask=(mono>0).astype(np.float32)
        eta=inputs['eta'].reshape(len(kx),-1)
        for U in ('FROZEN','NATIVE_UPDATE'):
            for cell,(C,G) in {'A':(1,1),'B':(1,0),'C':(0,1),'D':(0,0)}.items():
                with np.load(io.BytesIO(archive.extractfile('./'+U+'_'+cell+'.npz').read()),allow_pickle=False) as data:
                    for it in (1,2):
                        p='iter%d_'%it
                        before=data[p+'disps_before'][kx].reshape(len(kx),-1)
                        C_expected=data[p+'C_geometry']+C*mask*alpha+(1-C*mask)*eta
                        w_expected=data[p+'w_geometry']-G*mask*alpha*(before-mono)
                        checks={'C_path':compare(data[p+'C'],C_expected),
                                'w_path':compare(data[p+'w'],w_expected),
                                'Q_inverse_C':compare(data[p+'Q'],1/data[p+'C']),
                                'H_A_minus_S':compare(data[p+'H_raw'],data[p+'A']-data[p+'schur_subtraction']),
                                'rhs_v_minus_Sb':compare(data[p+'rhs'],data[p+'v']-data[p+'schur_rhs_subtraction'])}
                        H=data[p+'H_raw'].copy();idx=np.diag_indices_from(H)
                        H[idx]+=np.float32(sc['ep'])+np.float32(sc['lm'])*H[idx]
                        checks['native_damping']=compare(data[p+'L_damped_raw'],H)
                        E=data[p+'E'].astype(np.float64);Q=data[p+'Q'].astype(np.float64);w=data[p+'w'].astype(np.float64)
                        S,sb=schur_from_cross_blocks(E,Q,w,source,target,kx,sc['t0'],sc['t1'])
                        schur_check=compare(data[p+'schur_subtraction'],S)
                        rhs_check=compare(data[p+'schur_rhs_subtraction'],sb)
                        coupling=native_depth_coupling(E,data[p+'dx'],source,target,kx,sc['t0'])
                        dz_expected=Q*(w-coupling)
                        dz_check=compare(data[p+'dz'],dz_expected)
                        after_expected=data[p+'disps_before'].copy()
                        after_expected[kx]+=(data[p+'dz']).reshape(after_expected[kx].shape)
                        checks['native_disparity_writeback']=compare(data[p+'disps_after'],after_expected)
                        for name,check in checks.items():
                            formulas.append({**base,'U_mode':U,'cell':cell,'iteration':it,'formula':name,**check})
                        for name,check in [('Schur_matrix',schur_check),('Schur_rhs',rhs_check),('dz_native_guard',dz_check)]:
                            systems.append({**base,'U_mode':U,'cell':cell,'iteration':it,'formula':name,**check})
                        gate_before=np.clip(1/np.maximum(45*data[p+'U_before']-35,.1),0,1)
                        gate_after=np.clip(1/np.maximum(45*data[p+'U_after']-35,.1),0,1)
                        prior_rhs=-mask*alpha*(before-mono)
                        geom_rhs=data[p+'w_geometry']
                        norm_product=float(np.linalg.norm(prior_rhs)*np.linalg.norm(geom_rhs))
                        gates.append({**base,'U_mode':U,'cell':cell,'iteration':it,**boundary,
                                      'mean_source_gate_before':float(gate_before[inputs['ii']].mean()),
                                      'mean_source_gate_after':float(gate_after[inputs['ii']].mean()),
                                      'source_gate_change_norm':float(np.linalg.norm(gate_after[inputs['ii']]-gate_before[inputs['ii']])),
                                      'positive_prior_fraction':float(mask.mean()),
                                      'eta_median':float(np.median(eta)),
                                      'gamma_depth':float(alpha),
                                      'geometry_C_median':float(np.median(data[p+'C_geometry'])),
                                      'prior_gradient_norm':float(np.linalg.norm(mask*alpha*(before-mono))),
                                      'geometry_gradient_norm':float(np.linalg.norm(data[p+'w_geometry'])),
                                      'prior_geometry_depth_rhs_cosine':float(np.sum(prior_rhs*geom_rhs)/norm_product) if norm_product>0 else None,
                                      'hypothetical_postcall_clamp_changes':int(np.sum(data['final_disps']<1e-5)) if it==2 else '',
                                      'clamp_executed':False})
    return formulas,systems,gates

def csv_write(name,rows):
    with (ROOT/'05_analysis'/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader();writer.writerows(rows)

if __name__=='__main__':
    files=[pathlib.Path(p) for p in sys.argv[1:]] or sorted(RECEIVER.glob('result_*.tar'))
    all_rows=[[],[],[]]
    for path in files:
        for result,rows in zip(all_rows,verify(path)):result.extend(rows)
        print(json.dumps({'verified':path.name}),flush=True)
    for name,rows in zip(('NATIVE_FORMULA_CHECKS.csv','CPU_SCHUR_RECONSTRUCTION.csv','PRIOR_U_GATE_DIAGNOSTICS.csv'),all_rows):csv_write(name,rows)
    print(json.dumps({'archives':len(files),'row_counts':[len(r) for r in all_rows]}))
