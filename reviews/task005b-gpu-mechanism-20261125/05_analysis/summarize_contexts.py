"""Compact same-context mechanism comparisons and per-pose native updates."""
import pathlib,sys,json,csv
import numpy as np
from analyze_native import ROOT,RECEIVER,load_archive,reprojection,qmat

def csv_write(name,rows):
    if not rows:return
    with (ROOT/'05_analysis'/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader();writer.writerows(rows)

def camera_centers(poses):
    return np.array([-qmat(p[3:]).T@p[:3] for p in poses])

def summarize(archive):
    content=load_archive(archive);identity=content['INPUT_IDENTITY.json'];inp=content['COMMON_INPUTS.npz']
    meta=identity['provenance'];sc=identity['scalars'];ids=identity['slot_rgb_tokens']
    base={k:meta[k] for k in ('arm','D_origin','schedule','rgb')}
    out=[];pose_rows=[];endpoints=[]
    for endpoint in content['SUCCESS.json']['endpoint_checks']:
        endpoints.append({**base,'state_sha256':identity['state_sha256'],'tag':endpoint['tag'],'PASS':endpoint['PASS'],**{'max_abs_'+k:v for k,v in endpoint['max_abs'].items()},'atol':endpoint['atol'],'rtol':endpoint['rtol']})
    for U in ('FROZEN','NATIVE_UPDATE'):
        cells={c:content[U+'_'+c+'.npz'] for c in 'ABCD'}
        for it in (1,2):
            p='iter%d_'%it
            v={c:cells[c][p+'dx'].astype(np.float64) for c in 'ABCD'}
            initial,initial_ok=reprojection(inp['poses'],inp['disps'],inp['ii'],inp['jj'],inp['intrinsics'])
            uv_A,ok_A=reprojection(cells['A'][p+'poses_after'],cells['A'][p+'disps_after'],inp['ii'],inp['jj'],inp['intrinsics'])
            uv_D,ok_D=reprojection(cells['D'][p+'poses_after'],cells['D'][p+'disps_after'],inp['ii'],inp['jj'],inp['intrinsics'])
            support=(initial_ok&ok_A&ok_D)[:,None]
            gate=np.clip(1/np.maximum(45*inp['uncertainties'][inp['ii']]-35,.1),0,1)
            weight=.001*inp['weights']*gate[:,None]
            loss=lambda pred:float(np.sum(weight*support*(inp['targets']-pred)**2))
            gradient_metric=v['A']-v['B'];gradient_eta=v['C']-v['D']
            curvature_with_gradient=v['A']-v['C'];curvature_no_gradient=v['B']-v['D']
            inter=v['A']-v['B']-v['C']+v['D'];total=v['A']-v['D']
            n=lambda vector:float(np.linalg.norm(vector[:,:3]))
            ratio=lambda x,y:float(x/y) if y else None
            out.append({**base,'U_mode':U,'iteration':it,
                        'A_translation_dx_norm':n(v['A']),'B_translation_dx_norm':n(v['B']),
                        'C_translation_dx_norm':n(v['C']),'D_translation_dx_norm':n(v['D']),
                        'total_A_minus_D_translation_norm':n(total),
                        'curvature_no_gradient_B_minus_D_norm':n(curvature_no_gradient),
                        'gradient_at_metric_curvature_A_minus_B_norm':n(gradient_metric),
                        'gradient_at_eta_curvature_C_minus_D_norm':n(gradient_eta),
                        'gradient_amplification_eta_over_metric':ratio(n(gradient_eta),n(gradient_metric)),
                        'interaction_translation_norm':n(inter),
                        'interaction_to_total_norm_ratio':ratio(n(inter),n(total)),
                        'A_D_pair_support_fraction':float(np.mean(support)),
                        'A_D_pair_fixed_loss_before':loss(initial),
                        'A_D_pair_fixed_loss_A':loss(uv_A),'A_D_pair_fixed_loss_D':loss(uv_D),
                        'A_D_pair_loss_A_minus_D':loss(uv_A)-loss(uv_D),
                        'same_linearization':it==1,
                        'dx_norm_is_not_accuracy':True})
            for c,z in cells.items():
                before= camera_centers(z[p+'poses_before'])
                after= camera_centers(z[p+'poses_after'])
                for row,slot in enumerate(range(sc['t0'],sc['t1'])):
                    delta=v[c][row]
                    pose_rows.append({**base,'U_mode':U,'cell':c,'iteration':it,
                                      'pose_slot':slot,'RGB_token':ids[slot],
                                      **{'dx_'+axis:float(delta[i]) for i,axis in enumerate(('tx','ty','tz','rx','ry','rz'))},
                                      'camera_center_update_norm':float(np.linalg.norm(after[slot]-before[slot])),
                                      'native_W2C_se3_tangent':True})
    return out,pose_rows,endpoints

if __name__=='__main__':
    all_rows=[[],[],[]]
    for path in sorted(RECEIVER.glob('result_*.tar')):
        for rows,result in zip(all_rows,summarize(path)):rows.extend(result)
    for name,rows in zip(('CONTEXT_MECHANISM_SUMMARY.csv','PER_POSE_NATIVE_UPDATES.csv','ORIGINAL_ENDPOINT_EQUIVALENCE.csv'),all_rows):csv_write(name,rows)
    print(json.dumps({'states':len(list(RECEIVER.glob('result_*.tar'))),'rows':[len(x) for x in all_rows]}))
