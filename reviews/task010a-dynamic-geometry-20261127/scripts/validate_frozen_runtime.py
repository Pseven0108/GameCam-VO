"""Independent all-run identity/config/state checks, never repair results."""
import hashlib
import json
from pathlib import Path
import numpy as np
import yaml

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def flatten(value,prefix=''):
    result={}
    for key,item in value.items():
        name=prefix+'.'+key if prefix else key
        if isinstance(item,dict):result.update(flatten(item,name))
        else:result[name]=item
    return result


def main():
    selection=json.loads((TASK/'09_reproducibility/TRANSFER_SELECTION_FROZEN.json').read_text())
    if hashlib.sha256((TASK/'private/DATA_MANIFEST.json').read_bytes()).hexdigest()!=selection['dataset_manifest_sha256']:
        raise RuntimeError('Dataset identity changed')
    roster={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
    configs={};checks=[];identities=set()
    directories=sorted((TASK/'outputs/droid').glob('*'))
    for p in directories:
        file=p/'receipt.json'
        if not file.exists():continue  # separately preserved pre-model metadata failure
        r=json.loads(file.read_text())
        if r['status']!='COMPLETE':continue
        cfg=flatten(yaml.safe_load((p/'native_config.yaml').read_text()));cfg.pop('data.output',None)
        configs[(r['dataset'],r['seed'],r['method'])]=cfg
        with np.load(p/'trajectory.npz',allow_pickle=False) as z:
            ids=z['rgb_ids'];poses=z['c2w']
        if ids.tolist()!=roster[r['dataset']]['rgb_ids'] or len(set(ids.tolist()))!=32:
            raise RuntimeError('Frame/coverage mismatch '+p.name)
        if not np.isfinite(poses).all():raise RuntimeError('Nonfinite final poses '+p.name)
        rot=poses[:,:3,:3];orth=float(np.max(abs(np.swapaxes(rot,1,2)@rot-np.eye(3))))
        det=float(np.max(abs(np.linalg.det(rot)-1)))
        if orth>1e-4 or det>1e-4:raise RuntimeError('Invalid rotations '+p.name)
        with np.load(p/'keyframes.npz',allow_pickle=False) as z:
            if not all(np.isfinite(z[k]).all() for k in z.files):raise RuntimeError('Nonfinite keyframe state '+p.name)
            negative=int((z['disps']<0).sum());floor=int((z['disps']<=1.00001e-5).sum())
        if negative:raise RuntimeError('Unclamped negative final disparities '+p.name)
        calls=(p/'native_ba_observations/calls.jsonl').read_text().splitlines()
        if len(calls)!=r['native_ba_calls']:raise RuntimeError('Incomplete native log '+p.name)
        identities.add((r['native_extension_sha256'],r['checkpoint_sha256']))
        checks.append({'run':p.name,'frames':32,'orthogonality_max_abs':orth,'determinant_max_abs':det,
            'negative_final_disparities':negative,'final_floor_disparity_count':floor,'native_log_calls':len(calls),'status':'PASS'})
    paired=0
    for name in selection['heldout_windows']:
        for seed in [43,44,45]:
            base=configs[name,seed,'baseline']
            for method in selection['heldout_primary_methods']:
                if configs[name,seed,method]!=base:raise RuntimeError('Unexpected YAML difference '+name+'/'+method)
                paired+=1
    if len(identities)!=1:raise RuntimeError('Native extension/tracker identity differs')
    result={'status':'PASS','native_successful_runs_checked':len(checks),'heldout_configs_checked':paired,
        'config_differences_excluding_output_path':0,'same_native_extension_and_tracker':True,
        'checks':checks,'no_results_repaired':True,'scope':'Identity, numerical validity and comparability; not a certificate of motion or depth accuracy'}
    (TASK/'09_reproducibility/FROZEN_RUNTIME_VALIDATION.json').write_text(json.dumps(result,indent=2))
    print('Frozen runtime validation PASS',len(checks),'runs',paired,'matched configurations')


if __name__=='__main__':main()
