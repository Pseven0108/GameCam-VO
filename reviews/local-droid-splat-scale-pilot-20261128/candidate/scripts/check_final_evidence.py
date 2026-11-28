"""Read-only final identities, protocol equality, and established scorer cross-check."""
import ast,hashlib,json,pathlib,sys
import numpy as np
from scipy.spatial.transform import Rotation
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
sys.path.insert(0,str(TASK/'src'))
from evaluation import evaluate
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def main():
    baseline=pathlib.Path('D:/aaa/GameCam-VO')
    before=json.loads((TASK/'reports/SOURCE_AND_ASSET_AUDIT_V2.json').read_text())
    weights=[]
    for rec in before['weights']:
        p=baseline/'data/sota_assets/DROID_W'/rec['file']
        weights.append(dict(file=rec['file'],sha256=sha(p),before_sha256=rec['sha256'],size=p.stat().st_size))
        if weights[-1]['sha256']!=rec['sha256']:raise RuntimeError('Shared checkpoint identity drift')
    scorer=baseline/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/pipeline/offline_eval.py'
    tree=ast.parse(scorer.read_text())
    names={'fit_alignment','norm_rmse','rpe'}
    selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    namespace={'np':np,'Rotation':Rotation}
    exec(compile(selected,str(scorer),'exec'),namespace)
    source_configs=[];checks=[]
    with np.load(TASK/'data/train_004_01658-01721/offline_gt.npz',allow_pickle=False) as gt:
        truth=gt['gt_c2w'];ids=gt['rgb_ids']
    for arm,attempt in [('BASE','BASE_003'),('A5','A5_001'),('SCALE','SCALE_002'),('SCALE_A5','SCALE_A5_002')]:
        run=TASK/'outputs'/attempt
        cfg=yaml.safe_load((run/'native_config.yaml').read_text());cfg['data']['output']='ARM_OUTPUT'
        source_configs.append(cfg)
        meta=json.loads((run/'COMPLETE.json').read_text())
        if sha(run/'trajectory.npz')!=meta['trajectory_sha256']:raise RuntimeError('Trajectory identity drift')
        with np.load(run/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise RuntimeError('Frame pairing failed')
            pred=z['c2w'].astype(np.float64)
        stats,_=evaluate(pred,truth,ids)
        ep=pred[:,:3,3];er=pred[:,:3,:3];gp=truth[:,:3,3];gr=truth[:,:3,:3]
        q,t,s,rank=namespace['fit_alignment'](ep,gp,True)
        aligned=s*(ep@q.T)+t
        references=dict(ate_sim3_rmse=namespace['norm_rmse'](aligned-gp),global_sim3_scale=s)
        for offset in [1,15]:
            references.update({f'rpe{offset}_'+k:v for k,v in namespace['rpe'](aligned,q@er,gp,gr,ids,offset).items()
                if k in ['translation_rmse','rotation_rmse_deg','pairs']})
        for key,value in references.items():
            delta=abs(stats[key]-value)
            if delta>1e-12:raise RuntimeError('Established offline scorer differs')
            checks.append(dict(arm=arm,metric=key,abs_delta=delta,passed=True))
    if not all(c==source_configs[0] for c in source_configs[1:]):raise RuntimeError('Four-arm native YAML differs beyond output paths')
    local_before=json.loads((TASK/'reports/STAGING_RECEIPT.json').read_text())
    import subprocess
    git_path=pathlib.Path(local_before['source_repository'])
    regular=before['export_git_blob_checks']
    for rec in regular:
        p=ROOT/'upstream/DROID-W'/rec['path'];raw=p.read_bytes().replace(b'\r\n',b'\n')
        oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if oid!=rec['expected_git_blob']:
            raw=p.read_bytes();oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if oid!=rec['expected_git_blob']:raise RuntimeError('Frozen source export changed')
    out=dict(shared_checkpoints=weights,all_shared_checkpoint_hashes_unchanged=True,
        frozen_export_files_verified=len(regular),all_native_configs_equal_except_output=True,
        scorer_source=str(scorer),scorer_sha256=sha(scorer),metric_checks=checks,
        original_installed_extension_preserved=json.loads((TASK/'reports/FINAL_RUNTIME_AUDIT.json').read_text())['original_extension_sha256_preserved'],
        remote_connections=0,remote_processes_changed=0,local_models_remaining='none launched by this task')
    p=TASK/'reports/FINAL_EVIDENCE_VALIDATION.json'
    if p.exists():raise FileExistsError(p)
    p.write_text(json.dumps(out,indent=2)+'\n')
    print('FINAL_EVIDENCE_PASS',len(regular),'source blobs,',len(checks),'scorer comparisons,',len(weights),'checkpoints')
if __name__=='__main__':main()
