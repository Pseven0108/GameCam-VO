"""Create a new bounded experiment; read prior local assets without changing them."""
import hashlib,json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parent
PREV=ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE'
TASK=ROOT/'candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    for folder in ['scripts','src','tests','native','configs','reports','outputs','data']:
        (TASK/folder).mkdir(parents=True,exist_ok=True)
    for folder in ['build','tmp','cache','native_api_compat']:(ROOT/'toolchain'/folder).mkdir(parents=True,exist_ok=True)
    shutil.copytree(PREV/'upstream/DROID-W',ROOT/'upstream/DROID-W')
    for n in ['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']:
        shutil.copyfile(PREV/'candidate/native'/n,TASK/'native'/n)
    for n in ['evaluation.py','endpoint_check.py']:
        shutil.copyfile(PREV/'candidate/src'/n,TASK/'src'/n)
    # These copied utilities are changed only in this new candidate workspace.
    runtime=(PREV/'candidate/scripts/runtime_local.py').read_text()
    runtime=runtime.replace("DATA=TASK/'data/train_004_01658-01721'", "PREVIOUS=ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE'\nDATA=PREVIOUS/'candidate/data/train_004_01658-01721'")
    runtime=runtime.replace("CACHE=TASK/'cache/train_004_01658-01721'", "CACHE=PREVIOUS/'candidate/cache/train_004_01658-01721'")
    (TASK/'scripts/runtime_local.py').write_text(runtime)
    launch=(PREV/'candidate/scripts/run_wsl.py').read_text().replace('GameCam-VO-DROID-SPLAT-CANDIDATE','GameCam-VO-MPSFM-ROBUST-CANDIDATE')
    (TASK/'scripts/run_wsl.py').write_text(launch)
    build=(PREV/'candidate/scripts/build_local.py').read_text().replace('a5_sm120_001','robust_sm120_001').replace('local_a5_splat_c3414af6','local_mpsfm_robust_c3414af6').replace('LOCAL_A5_BUILD','LOCAL_ROBUST_BUILD')
    (TASK/'scripts/build_local.py').write_text(build)
    for n in ['INPUT_MANIFEST.json','offline_gt.npz']:
        folder=TASK/'data/train_004_01658-01721';folder.mkdir(exist_ok=True)
        shutil.copyfile(PREV/'candidate/data/train_004_01658-01721'/n,folder/n)
    for n in ['source_audit.py','final_runtime_audit.py']:
        shutil.copyfile(PREV/'candidate/scripts'/n,TASK/'scripts'/n)
    protocol=dict(task='MP-SfM Cauchy transfer into isolated DROID-W',
        source_mpsfm='fa49640862391437865b2fd89ca3db3e6948b63b',
        source_droid_w='c3414af6047d06bafc1a6645d09f23247f3b2cdc',
        input_window='VIPER Train Day004 RGB1658-1721',camera_mapping='RGB-1',frames=64,
        seed=43,stride=1,image_size=[360,640],local_buffer=96,arms=['BASE','A5','ROBUST','ROBUST_A5'],
        gamma_depth=0.01,robust_family='Cauchy IRLS on native linear disparity residual',
        robust_relative_scale=0.1,scale_origin='2 * official m3dv2-large relative uncertainty floor 0.05; first-order depth-to-disparity relative propagation',
        scale_epsilon_disparity=1e-6,
        objective='0.5*m*a*alpha*tau^2*log1p((d-dm)^2/tau^2)',
        local_damping='(1-m*a)*eta independent of residual-dependent q',
        equation_C='Cg+m*a*alpha*q+(1-m*a)*eta',equation_b='bg-m*a*alpha*q*(d-dm)',
        q='1/(1+((d-dm)/tau)^2)',tau='max(0.1*abs(dm),1e-6)',
        scope='Frontend Main-loop Local BA only; recalculate q inside EACH native inner iteration',
        preserved=['raw Metric3D targets','native initialization','U/UBA','Final BA','Trajectory Filler','frozen checkpoints','existing source and installed extensions'],
        not_transferred=['MP-SfM log-depth residual','calibrated pixel variances','MAD scale adaptation','SfM registration','cross-view occlusion checks','scale/shift correction'],
        comparison='new four complete trajectories, one seed; no parameter search or performance-selected reruns',
        primary_metric='whole-window global Sim3 ATE RMSE; compare ROBUST vs BASE and ROBUST_A5 vs A5',
        secondary=['SE3 ATE','RPE offset1/15 using ONE complete-window global Sim3 scale','keyframe identity','negative disparity and clamp counters','runtime and memory'],
        scope_limit='development-window evidence only, not cross-scene/generalization evidence',remote_connections=0,
        reuse='read-only existing local RGB, cached Metric3D native/flip/confidence and FiT3D; no new model forwards needed')
    (TASK/'configs/PROTOCOL.json').write_text(json.dumps(protocol,indent=2)+'\n')
    upstream=ROOT/'upstream/mpsfm'
    head=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
    if head!=protocol['source_mpsfm']:raise RuntimeError('Unapproved MP-SfM revision')
    selected=['mpsfm/sfm/mapper/bundle_adjustment.py','mpsfm/sfm/scene/image/depth.py','configs/defaults/m3dv2-large.yaml','mpsfm/extraction/imagewise/geometry/models/depth/metric3dv2.py','LICENSE','README.md']
    receipt=dict(head=head,selected_source_files=[dict(path=n,sha256=sha(upstream/n)) for n in selected],
        protocol_sha256=sha(TASK/'configs/PROTOCOL.json'),existing_cache_reused_read_only=True,remote_connections=0)
    (TASK/'reports/STAGING_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
