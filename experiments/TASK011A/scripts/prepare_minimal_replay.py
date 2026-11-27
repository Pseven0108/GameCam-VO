"""Publish only the frozen prediction fields needed for a self-contained audit."""
from common import *

def main():
    out=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path'])
    dest=out/'minimal_replay_inputs';dest.mkdir(exist_ok=False)
    scale=json.loads((out/'SCALES_AND_STATUS.json').read_text())['scales']['R2_2_BILINEAR_SAME_FOCAL']
    index=[]
    for row in records():
        item=row['sample'];sid=item['sample_id']
        with np.load(row['local_npz'],allow_pickle=False) as z:
            fields={k:z[k].copy() for k in ['native_depth','native_confidence','flip_depth']}
        if item['dataset']=='MVS-Synth':
            with np.load(RESTORED/'02_restoration/torch_CPU'/(sid+'.npz'),allow_pickle=False) as z:
                for key in ['native_bilinear_same_focal','flip_bilinear_same_focal']:fields[key]=z[key].copy()
            gt=ground_truth(row);valid=np.isfinite(gt)&(gt>0)
            error=np.full(gt.shape,np.nan);p=fields['native_bilinear_same_focal'].astype(float)
            error[valid]=np.abs(p[valid]*scale-gt[valid])/(gt[valid]+1e-12)
            fields['AbsRel_sensitivity']=error
        target=dest/(sid+'.npz');np.savez_compressed(target,**fields)
        index.append({'sample_id':sid,'dataset':item['dataset'],'sequence':item['sequence_id'],'source_raw_cache_sha256':row['sha256'],'sha256':sha(target),'bytes':target.stat().st_size,'contains_raw_GT':False,'contains_RGB':False,'new_model_inference':False})
    dump(out/'MINIMAL_REPLAY_INPUT_INDEX.json',index)
    print('MINIMAL_REPLAY_INPUTS_READY',len(index),sum(r['bytes'] for r in index),'bytes')

if __name__=='__main__':main()
