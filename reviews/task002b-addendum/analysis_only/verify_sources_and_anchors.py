"""Verify source identity and compare common keyframe pairs using direct BA anchors."""
import json
from collections import defaultdict
from hashlib import sha1
from zipfile import ZipFile

from metrics import CASE, EXP, MODELS, OUT, np, relative
from audit_common import AUDIT1, COMMITS, OFFSETS, R1, R2, SOURCES, ZIP, ZIP_SHA
from audit_common import digest, exact_member, load_contract, read_csv, read_json, require, sha
from audit_motion import gt_checks, prepare_evaluator
from decompose import load_export, write_csv, write_json
from aggregate import sequence_compare
from scipy.spatial.transform import Rotation

SOURCE_RANGES = {
    ('DROID-SLAM', 'droid_slam/droid.py'): [(71, 85)],
    ('DROID-SLAM', 'droid_slam/trajectory_filler.py'): [(50, 84), (97, 110)],
    ('DROID-SLAM', 'droid_slam/depth_video.py'): [(213, 225)],
    ('DROID-SLAM', 'droid_slam/factor_graph.py'): [],
    ('DROID-SLAM', 'src/droid_kernels.cu'): [(1394, 1402)],
    ('DROID-W', 'src/trajectory_filler.py'): [(31, 35), (53, 95), (115, 142)],
    ('DROID-W', 'src/utils/eval_traj.py'): [(143, 165)],
    ('DROID-W', 'src/slam.py'): [(127, 151), (174, 179), (217, 227)],
    ('DROID-W', 'src/depth_video.py'): [(333, 378)],
    ('DROID-W', 'src/factor_graph.py'): [(267, 281)],
    ('DROID-W', 'src/lib/droid_kernels.cu'): [(323, 336), (1867, 1874), (1915, 1920)],
    ('DROID-W', 'src/lib/droid.cpp'): [],
    ('DROID-W', 'src/utils/mono_priors/img_feature_extractors.py'): [(68, 88)],
}
KK = 'KEYFRAME->KEYFRAME'


def source_audit(z):
    table = AUDIT1 / 'SOURCE_ENTRY_VERIFICATION.csv'
    index = {(x['repository'], x['path']): x for x in read_csv(table)}
    rows, excerpts = [], []

    def excerpt(path, label, raw, ranges):
        if not ranges:
            return
        lines = raw.decode('utf-8').splitlines()
        excerpts.append(f'[{label}] {path}  SHA-256={sha(raw)}')
        for lo, hi in ranges:
            require(hi <= len(lines), f'line bound: {path} {lo}-{hi}')
            excerpts.append(f'  lines {lo}-{hi}')
            excerpts.extend(f'{i:5d}  {lines[i-1]}' for i in range(lo, hi+1))
        excerpts.append('')

    for (repo, rel), ranges in SOURCE_RANGES.items():
        p = SOURCES / repo / rel
        raw = p.read_bytes()
        g = sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        rec = index[repo, rel]
        require(g == rec['git_sha1'] and len(raw) == int(rec['bytes']) and
                rec['check'] == 'ARCHIVE_AND_SNAPSHOT_BLOB_VERIFIED', f'frozen source drift: {p}')
        rows.append(dict(model=repo, commit=COMMITS[repo], local_path=str(p), relative_path=rel,
                         git_blob_sha1=g, sha256=sha(raw), bytes=len(raw), proof=str(table),
                         checked_line_ranges=';'.join(f'{a}-{b}' for a,b in ranges), status='MATCH'))
        excerpt(f'{repo}/{rel}', COMMITS[repo], raw, ranges)

    for p, expected, proof, ranges in [
        (R2/'pipeline/run_original.py', sha(exact_member(z, 'pipeline/run_original.py')),
         'byte-identical to sealed R2 ZIP member', [(118, 137)]),
        (R1/'pipeline/run_segment.py', '428ca308f9df4d9375251f463fb560673c323aa9e62c9a2fcc98ffa6e99180e6',
         'Task 002B checked runner SHA-256', [(155, 165), (210, 230)]),
    ]:
        raw = p.read_bytes()
        require(sha(raw) == expected, f'runner SHA drift: {p}')
        rows.append(dict(model='LOCAL_RUNNER', local_path=str(p), relative_path=f'{p.parent.parent.name}/{p.parent.name}/{p.name}',
                         sha256=expected, bytes=len(raw), proof=proof,
                         checked_line_ranges=';'.join(f'{a}-{b}' for a,b in ranges), status='MATCH'))
        excerpt(rows[-1]['relative_path'], proof, raw, ranges)

    write_csv('evidence/SOURCE_PROVENANCE.csv', rows)
    (OUT/'evidence/FILLER_SOURCE_EXCERPTS.txt').write_text('\n'.join(excerpts), encoding='utf-8')
    return len(rows)


def sensitivity(z):
    _, plans = load_contract(z)
    ev, loaders = prepare_evaluator(z)
    gt_hashes = json.loads(exact_member(z,'evidence/R1_PRESERVATION_AND_SCORE_CHECK.json'))['gt_file_sha256']
    stats = {(r['segment'],int(r['offset']),r['model']):r for r in read_csv(OUT/'RPE_BY_ENDPOINT_TYPE.csv')
             if r['population']=='MATCHED_CLASS_GRID' and r['slam_type']==r['wild_type']==KK}
    align = {(r['segment'],r['model']):r for r in read_csv(OUT/'evidence/R2_STAGE_AND_ALIGNMENT_INDEX.csv')}
    rows, details, totals = [], [], defaultdict(lambda: [0,0.,0.])

    for plan in plans:
        sid = plan['id']
        ids = np.arange(int(plan['first']), int(plan['last'])+1)
        truth, _ = gt_checks(plan,gt_hashes,loaders,ids)
        sl, wi = (load_export(z,plan,m,ids,{}) for m in MODELS)
        for name,d in zip(MODELS,(sl,wi)):
            recorded = align[sid,name]
            require(recorded['trajectory_sha256']==d['trajectory_sha256'], f'wrong saved alignment: {sid}')
            d['scale'] = float(recorded['alignment_scale'])
        common = sl['source'] & wi['source']
        to_key = np.cumsum(sl['source'])-1
        direct = sl['direct']
        sl_ba = dict(pred=direct,rot=Rotation.from_quat(direct[:,3:]).as_matrix(),scale=sl['scale'])
        loc = np.flatnonzero(sl['source'])
        for off in OFFSETS:
            i,j = ev.pairs(ids,off,sl['valid'] & wi['valid'])
            keep = common[i] & common[j]
            i,j = i[keep],j[keep]
            full = relative(ev,sl,truth,i,j)
            post = relative(ev,sl_ba,truth[loc],to_key[i],to_key[j])
            wild = relative(ev,wi,truth,i,j)
            meta = dict(segment=sid,sequence=plan['sequence'],environment=plan['environment'],
                        calibration_branch=plan['branch'],offset=off)
            for tag,v in [('SLAM_EXPORTED',full),('SLAM_DIRECT_BA',post),('W_FINAL_BA_REINSERTED',wild)]:
                tsse, rsse = float(v[:,0].sum()),float(np.square(v[:,1]).sum())
                if tag != 'SLAM_DIRECT_BA':
                    model = MODELS[1] if tag == 'W_FINAL_BA_REINSERTED' else MODELS[0]
                    prev = stats[sid,off,model]
                    require(len(v)==int(prev['valid_count']) and
                            np.allclose([tsse,rsse],[float(prev[k]) for k in ('translation_sse','rotation_sse')],
                                        rtol=1e-11,atol=1e-11),f'common K->K replay mismatch: {sid}/{off}/{tag}')
                rows.append(dict(**meta,pose_source=tag,pair_count=len(v),translation_sse=tsse,rotation_sse=rsse,
                                 translation_rmse=float(np.sqrt(tsse/len(v))) if len(v) else None,
                                 rotation_rmse_deg=float(np.sqrt(rsse/len(v))) if len(v) else None))
                acc=totals[plan['branch'],plan['environment'],plan['sequence'],off,tag]
                acc[0]+=len(v); acc[1]+=tsse; acc[2]+=rsse
            for a,b,old,new,w in zip(ids[i],ids[j],full,post,wild):
                details.append(dict(**meta,start_rgb=int(a),end_rgb=int(b),slam_scale=sl['scale'],wild_scale=wi['scale'],
                                    gt_displacement=old[2],slam_export_trans_rpe=float(np.sqrt(old[0])),
                                    slam_direct_trans_rpe=float(np.sqrt(new[0])),wild_anchor_trans_rpe=float(np.sqrt(w[0])),
                                    slam_export_rotation_deg=old[1],slam_direct_rotation_deg=new[1],wild_anchor_rotation_deg=w[1]))
    seqkeys=('calibration_branch','environment','sequence','offset','pose_source')
    seq=[dict(zip(seqkeys,k),valid_pairs_or_frames=n,translation_rmse=float(np.sqrt(t/n)) if n else None,
              rotation_rmse=float(np.sqrt(r/n)) if n else None) for k,(n,t,r) in sorted(totals.items())]
    summaries = []
    for a,b in [('SLAM_EXPORTED','SLAM_DIRECT_BA'),('SLAM_DIRECT_BA','W_FINAL_BA_REINSERTED')]:
        summaries.extend(sequence_compare(seq,('offset',),f'{b}_MINUS_{a}',(a,b),'pose_source',(a,b)))
    write_csv('MATCHED_KEYFRAME_ANCHOR_SENSITIVITY_BY_SEGMENT.csv',rows)
    write_csv('MATCHED_KEYFRAME_ANCHOR_PAIR_DETAIL.csv',details)
    write_csv('MATCHED_KEYFRAME_ANCHOR_SENSITIVITY.csv',summaries)
    return len(details),len([r for r in details if r['segment']==CASE]),len(stats)


def main():
    require(digest(ZIP)==ZIP_SHA, 'sealed trajectory archive changed')
    with ZipFile(ZIP) as z:
        n_sources = source_audit(z)
        n_pairs, n_case, replay = sensitivity(z)
    identity = EXP/'VIPER_VAL007_STAGE_OBSERVABILITY_R2/review/INPUT_IDENTITY_CHECK.json'
    obs = read_json(identity)
    require(obs['stride']==4 and obs['admitted_rgb']==122 and obs['original_rgb']==487, 'old observer identity drift')
    write_json('evidence/SOURCE_AND_ANCHOR_VERIFICATION.json',dict(status='PASS',verified_source_files=n_sources,
        shared_keyframe_endpoint_pairs=n_pairs,shared_pairs_in_val007=n_case,replayed_previous_count_sse_cells=replay,
        scale_fitted_again=False,old_observer=dict(path=str(identity),sha256=digest(identity),stride=obs['stride'],
        original_frames=obs['original_rgb'],sampled_frames=obs['admitted_rgb'],use='historical context only; not current stride=1 evidence'),
        historical_source_index_sha256=digest(AUDIT1/'SOURCE_ENTRY_VERIFICATION.csv')))
    print(f'PASS: {n_sources} frozen source/runner identities; {n_pairs} shared K->K pairs; {replay} prior count/SSE rows')


if __name__ == '__main__':
    main()
