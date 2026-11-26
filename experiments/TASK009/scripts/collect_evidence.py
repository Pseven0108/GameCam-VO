"""Read-only identities for task sources, checkpoints and protected user files."""
import hashlib
import difflib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=Path(r'D:\aaa\GameCam-VO')
OUT=ROOT/'experiments/TASK009/intake'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    repositories={
        'DROID-W':ROOT/'external/DROID-W',
        'BA-Track':ORIGINAL/'baselines/ba_track/upstream',
        'WildGS-SLAM':ORIGINAL/'baselines/wildgs_slam/upstream',
        'Pi3MOS-local-reference':ORIGINAL/'baselines/pi3mos/upstream',
        'Metric3D':ROOT/'external/Metric3D','FiT3D':ROOT/'external/FiT3D',
        'Easi3R':ROOT/'external/Easi3R','LEAP-VO':ROOT/'external/LEAP-VO'}
    sources={}
    for name,path in repositories.items():
        result=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True,check=True)
        licenses=[]
        for candidate in sorted(path.glob('*LICENSE*'))+sorted(path.glob('*COPYING*')):
            if candidate.is_file():licenses.append({'file':candidate.name,'sha256':sha(candidate),'opening':candidate.read_text(errors='replace')[:350]})
        sources[name]={'head':result.stdout.strip(),'path':str(path),'root_licenses':licenses}
    (OUT/'source_identities.json').write_text(json.dumps(sources,indent=2))
    weights=ORIGINAL/'experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/fresh_official_downloads'
    checkpoint_rows=[]
    for filename in ('droid.pth','metric_depth_vit_large_800k.pth','dinov2_reg_small_finetuned.pth'):
        path=weights/filename
        checkpoint_rows.append({'name':filename,'bytes':path.stat().st_size,'sha256':sha(path),'path':str(path),'read_only_reuse':True})
    (OUT/'native_prior_checkpoint_provenance_supplement.json').write_text(json.dumps({
        'purpose':'Supplement the R3 depth-reuse receipt without rewriting it',
        'checkpoints':checkpoint_rows,'metric3d_expected_sha256':'15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972',
        'actual_metric3d_matches':checkpoint_rows[1]['sha256']=='15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972',
        'depth_generation_evidence':'native_priors_r2.log; reused outputs have per-file SHA in native_priors_216x384_r3/receipt.json',
        'no_new_metric_inference':True},indent=2))
    protected=json.loads((OUT/'protected_user_files.json').read_text())
    comparison=[{'path':p,'before':h,'after':sha(ORIGINAL/p)} for p,h in protected.items()]
    for row in comparison:row['unchanged']=row['before']==row['after']
    (OUT/'protected_user_files_after.json').write_text(json.dumps({'all_unchanged':all(x['unchanged'] for x in comparison),'files':comparison},indent=2))
    patch=subprocess.run(['git','-C',str(ROOT/'external/DROID-W'),'diff','--','setup.py','src'],capture_output=True,check=True).stdout
    (OUT/'droid_candidate_compatibility.patch').write_bytes(patch)
    # This candidate is an exported archive, not an independent Git checkout.
    # `git -C ... diff` would silently find the outer DROID repository instead.
    original_lietorch=ORIGINAL/'baselines/droid_w/upstream/thirdparty/lietorch'
    candidate_lietorch=ROOT/'external/DROID-W/thirdparty/lietorch'
    pieces=[];identities=[]
    for relative in ('setup.py','lietorch/src/lietorch_cpu.cpp','lietorch/src/lietorch_gpu.cu','lietorch/extras/corr_index_kernel.cu'):
        original_bytes=subprocess.check_output(['git','-C',str(original_lietorch),'show',f'0fa9ce8ffca86d985eca9e189a99690d6f3d4df6:{relative}'])
        candidate_bytes=(candidate_lietorch/relative).read_bytes()
        pieces.extend(difflib.unified_diff(original_bytes.decode().splitlines(keepends=True),candidate_bytes.decode().splitlines(keepends=True),fromfile='a/'+relative,tofile='b/'+relative))
        identities.append(dict(file=relative,before_sha256=hashlib.sha256(original_bytes).hexdigest(),after_sha256=hashlib.sha256(candidate_bytes).hexdigest()))
    (OUT/'lietorch_candidate_compatibility.patch').write_text(''.join(pieces),encoding='utf-8')
    (OUT/'lietorch_archive_source_identity.json').write_text(json.dumps(dict(source_commit='0fa9ce8ffca86d985eca9e189a99690d6f3d4df6',
        eigen_commit='824272cde8ca2541e8b67b0887f5ded92b128d1f',candidate_is_exported_archive=True,files=identities),indent=2))
    print(json.dumps({'sources':len(sources),'checkpoints':len(checkpoint_rows),'protected_files_unchanged':all(x['unchanged'] for x in comparison)}))


if __name__=='__main__':main()
