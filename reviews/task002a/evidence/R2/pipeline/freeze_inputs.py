"""Verify the frozen R1 Validation evidence and create the R2 worklist."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import zipfile

import numpy as np

from constants import BUFFER, FIXED, SLAM_COMMIT, VARIABLE
from offline_evaluation import ALIGNMENT_STAMP, OFFSETS, metrics, selfcheck
from segment_input import checked_manifest
from transfer_common import DROID_W_COMMIT, ROOT, csv_write, digest, dump, load, rows

WILD = ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
METRIC_FIELDS = ('ate_sim3_game_units','ate_se3_game_units','ate_sim3_path_pct','scale_est_to_gt')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def freeze(z, identity):
    audited = {}
    archive_index = json.loads(z.read('FILE_SHA256_MANIFEST.json'))
    index = {r['path']:r for r in archive_index['files']}
    require(z.testzip() is None, 'R1 ZIP CRC')
    require(archive_index == load(WILD/'FILE_SHA256_MANIFEST.json'), 'R1 SHA index')

    def sealed(rel):
        p = WILD/rel
        actual = digest(p)
        require(actual == index[rel]['sha256'] and z.read(rel) == p.read_bytes(), f'R1 evidence differs: {rel}')
        audited[rel] = actual
        return p

    contract = load(sealed('evaluation/EVALUATION_CONTRACT.json'))
    require(contract['source_sha256'] == digest(ROOT/'pipeline/offline_evaluation.py')
            and contract['metric_version'] == ALIGNMENT_STAMP and contract['rpe_offsets'] == list(OFFSETS), 'evaluator identity')
    active, terminal = {}, {}
    for name in ('FULL_PLAN.json','FULL_RESOURCE_01_PLAN.json'):
        p = sealed(name)
        plan = load(p)
        ledger = load(sealed(f'evidence/{plan["kind"]}-results.json'))
        require(ledger['plan_sha256'] == digest(p) == contract['plan_sha256'][name], 'R1 ledger/plan lock')
        for old in plan.get('supersedes', []):
            del active[old]
        for s in plan['segments']:
            require(s['id'] not in active, 'duplicate segment')
            active[s['id']] = s
        terminal.update({r['segment']:r for r in ledger['results']})
    selected = sorted((s for s in active.values() if s['sequence'].startswith('val_')), key=lambda s:(s['sequence'],s['first']))
    listed = {r['id']:r for r in rows(sealed('FULL_SEGMENT_MANIFEST.csv')) if r['sequence'].startswith('val_')}
    scores = {r['segment']:r for r in rows(sealed('evaluation/DROIDW_VIPER_SEGMENT_EVALUATION.csv'))}
    seqs = {f'val_{r["sequence_id"]}':r for r in rows(sealed('VIPER_SEQUENCE_MANIFEST.csv')) if r['split']=='val'}
    truth_sources = {r['case']:r for r in load(sealed('evidence/camera_provenance.json'))['files']}
    require(len(seqs)==47 and len(selected)==92 and set(listed)=={s['id'] for s in selected}, 'Validation identity/size')
    require(Counter(s['branch'] for s in selected)=={FIXED:82,VARIABLE:10}, 'calibration group sizes')
    require({s['sequence'] for s in selected if s['branch']==VARIABLE}=={'val_042','val_043'}, 'Variable-K identity')
    coverage, references, workers, table = defaultdict(list), [], [], []

    for s in selected:
        sid, seq = s['id'], s['sequence']
        expected = list(range(s['first'], s['last']+1))
        coverage[seq].extend(expected)
        require(all(str(s[k])==v for k,v in listed[sid].items()), f'plan/CSV disagreement {sid}')
        manifest = sealed(f'manifests/{sid}.json')
        doc = checked_manifest(manifest)
        sha = s['input_manifest_sha256']
        require(digest(manifest)==sha and (doc['id'],doc['environment'],doc['branch'])==(sid,s['environment'],s['branch'])
                and [f['rgb_id'] for f in doc['frames']]==expected, f'RGB ordering or identity {sid}')
        original = terminal[sid]
        rel = Path(original['attempt'])
        require(rel.parts[:2]==('results',sid) and len(rel.parts)==3, 'bad attempt path')
        names = ('attempt.json','model_input.json','input_receipt.json','keyframes.json','tracking_child_ok.json',
                 'trajectory.npz','native_config.yaml')
        files = {n:sealed((rel/n).as_posix()) for n in names}
        a, inp, receipt, kf, child = (load(files[n]) for n in names[:5])
        k = np.asarray(inp['actual_loader_k'],np.float32)
        cast_k = np.asarray(np.asarray(doc['output_k'])*3.,np.float32)*np.float32(1/3.)
        require(np.array_equal(k,cast_k) and k.shape==(4,), f'effective float32 K {sid}')
        require(a==original and a['status']=='COMPLETE' and a['exit_code']==0
                and a['upstream_commit']==DROID_W_COMMIT and a['stride']==inp['stride']==1
                and sha==a['input_manifest_sha256']==inp['manifest_sha256']==receipt['input_manifest_sha256']
                and receipt['frames']==a['valid_poses']==child['read_frames']==child['filler_frames']==s['frames']==len(expected)
                and inp['rgb_ids']==expected and inp['size']==[640,360] and inp['pose_inputs']==0
                and a['scaled_rgb_tensor_sha256']==child['scaled_rgb_tensor_sha256'], f'R1 input receipt {sid}')
        traj = files['trajectory.npz']
        require(digest(traj)==a['trajectory_sha256'], f'trajectory hash {sid}')
        with np.load(traj,allow_pickle=False) as x:
            pose, ids, kids = x['c2w_xyzw'], x['rgb_ids'], x['keyframe_rgb_ids'].tolist()
            require(ids.tolist()==expected and x['valid'].shape==ids.shape and x['valid'].all()
                    and pose.shape==(len(ids),7) and np.isfinite(pose).all() and kids==kf['rgb_ids']==sorted(set(kids))
                    and len(kids)==kf['final_count']==a['keyframes'] and set(kids)<=set(expected), f'R1 pose integrity {sid}')
        sr = scores[sid]
        require(sr['status']=='COMPLETE' and int(sr['valid_poses'])==len(expected), f'R1 score coverage {sid}')
        dest = ROOT/'wild_reference'/sid
        dest.mkdir(parents=True,exist_ok=True)
        for name,p in files.items():
            (dest/name).write_bytes(p.read_bytes())
        (ROOT/'manifests'/manifest.name).write_bytes(manifest.read_bytes())
        workers.append(dict(**s,actual_loader_k=k.tolist(),wild_rgb_tensor_sha256=a['scaled_rgb_tensor_sha256']))
        references.append(sr)
        table.append(dict(**workers[-1],gt_sha256=truth_sources[seq]['gt_sha256'],wild_trajectory_sha256=digest(traj),
                          wild_config_sha256=digest(files['native_config.yaml']),**{f'wild_{key}':sr[key] for key in METRIC_FIELDS}))

    gt_hashes = {}
    for seq,m in seqs.items():
        expected = list(range(int(m['rgb_first']),int(m['rgb_last'])+1))
        require(coverage[seq]==expected and len(expected)==int(m['frames']), f'coverage differs {seq}')
        p = WILD/'offline_gt'/f'{seq}.npz'
        gt_hashes[seq] = digest(p)
        require(gt_hashes[seq]==truth_sources[seq]['gt_sha256'],f'GT SHA differs {seq}')
        with np.load(p,allow_pickle=False) as x:
            require(x['rgb_ids'].tolist()==expected and np.array_equal(x['camera_frame_ids'],x['rgb_ids']-1)
                    and x['c2w'].shape==(len(expected),4,4) and np.isfinite(x['c2w']).all(),f'GT index or shape {seq}')
    require(sum(map(len,coverage.values()))==49815,'Validation frame count differs')
    reproduced = []
    for seq in ('val_003','val_007','val_042','val_046'):
        s = next(s for s in selected if s['sequence']==seq)
        sid = s['id']
        with np.load(ROOT/'wild_reference'/sid/'trajectory.npz',allow_pickle=False) as p, \
             np.load(WILD/'offline_gt'/f'{seq}.npz',allow_pickle=False) as g:
            ids = p['rgb_ids']
            stat,rpe,_ = metrics(p['c2w_xyzw'],g['c2w'][ids-1],ids,p['valid'])
        np.testing.assert_allclose([stat[k] for k in METRIC_FIELDS],[float(scores[sid][k]) for k in METRIC_FIELDS],rtol=1e-10,atol=1e-10)
        reproduced.append(dict(segment=sid,metrics={k:stat[k] for k in METRIC_FIELDS},rpe_rows=len(rpe)))
    csv_write(ROOT/'VIPER_R2_FROZEN_VAL92_MANIFEST.csv',list(table[0]),table)
    csv_write(ROOT/'DROID_W_FROZEN_REFERENCE.csv',list(references[0]),references)
    worklist = ROOT/'evidence/IMMUTABLE_INPUT_WORKLIST.json'
    dump(worklist,dict(kind='VIPER_R2_VERIFIED_STRIDE1',segments=workers))
    lock = dict(protocol='VIPER_MATCHED_DUAL_BASELINE_R2_V1',source='reconciled sealed R1 terminal attempts and evidence',
                slam_commit=SLAM_COMMIT,wild_commit=DROID_W_COMMIT,segments=92,sequences=47,frames=49815,
                fixed_segments=82,fixed_sequences=45,variable_segments=10,variable_sequences=2,stride=1,image_wh=[640,360],
                initialization='independent per frozen segment',slam_entrypoint='official synchronous Droid (demo default)',
                visualization='upstream native viewer on the current private noVNC desktop; separate attempt record for any fallback',
                slam_buffer=BUFFER,pose_input_to_gpu=False,evaluation=contract,
                manifest_sha256=digest(ROOT/'VIPER_R2_FROZEN_VAL92_MANIFEST.csv'),rgb_worklist_sha256=digest(worklist),
                r1_review_sha256=identity,r1_evidence_files=len(audited))
    dump(ROOT/'PROTOCOL_LOCK.json',lock)
    dump(ROOT/'VIPER_R2_PROTOCOL_LOCK.json',lock)
    dump(ROOT/'evidence/R1_PRESERVATION_AND_SCORE_CHECK.json',dict(artifact_sha256=audited,all_rgb_ids=49815,
         gt_file_sha256=gt_hashes,reproduced=reproduced))
    print(f'PASS: {len(audited)} sealed artifacts, 92 segments, 47 sequences, 49815 poses; four scores reproduced')


if __name__ == '__main__':
    selfcheck()
    (ROOT/'manifests').mkdir(exist_ok=True)
    verification = load(WILD/'DELIVERY_VERIFICATION.json')
    bundle = WILD/verification['file']
    require(digest(bundle)==verification['sha256'],'R1 ZIP SHA differs')
    with zipfile.ZipFile(bundle) as z:
        freeze(z,verification['sha256'])
