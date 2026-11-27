"""Initialize independent TASK011C evidence, without model/GPU execution."""
import json
import shutil
import subprocess
from pathlib import Path

from common import BASE, PARENT, ROOT, TASK, dump, sha


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    if git('rev-parse','HEAD').decode().strip() != PARENT:
        raise RuntimeError('TASK011C must start at the exact reviewed TASK011B commit')
    intake = TASK / 'intake'
    intake.mkdir(parents=True, exist_ok=False)
    attachment = Path('C:/Users/Administrator/.codex/attachments/6da33d0b-80a5-48de-8ade-f99c35368132/已粘贴的文本.txt')
    shutil.copy2(attachment,intake/'TASK011C_USER_INSTRUCTION.txt')
    dependencies = []
    paths = ('CADP_DR_EXPERIMENTAL_BRANCH/controller.py','scripts/reliability.py')
    inherited = ROOT / 'experiments/TASK011B'
    for path in paths:
        rel = 'experiments/TASK011B/' + path
        content = git('show',PARENT + ':' + rel)
        if (inherited / path).read_bytes() != content:
            raise RuntimeError('Materialized inherited controller differs from fixed commit')
        dependencies.append(dict(path=path,sha256=sha(inherited/path)))
    all_files = git('ls-tree','-r','--name-only',PARENT,'experiments/TASK011B').decode().splitlines()
    protected = []
    for rel in all_files:
        p = ROOT / rel
        if p.is_file():
            if p.read_bytes() != git('show',PARENT + ':' + rel):
                raise RuntimeError('Inherited evidence differs from parent: '+rel)
            protected.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
    baseline = Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
    originals = []
    if baseline.exists():
        names = subprocess.check_output(['git','-C',str(baseline),'ls-files','src','configs','config','setup.py'],text=True).splitlines()
        for rel in names:
            p = baseline / rel
            if p.is_file():
                originals.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
    dump(intake/'INITIAL_ASSET_PROTECTION.json',dict(parent=PARENT,inherited=protected,
        original_baseline_files=originals,remote_not_contacted=True,
        model_weights_not_opened=True,baseline_environment_not_modified=True))
    dump(TASK/'configs/FROZEN_SOURCE_LOCK.json',dict(parent_commit=PARENT,
        controller_dependencies=dependencies,production_DROID_W_commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc',
        native_sources_reused_without_edit=True,CUDA_build_authorized=False))
    configs = {}
    for arm in ('A0','A1','A4','A5'):
        p = inherited / 'CADP_DR_CONFIGS' / (arm+'.json')
        target = TASK / 'configs/arms' / p.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
        configs[arm] = dict(sha256=sha(target),byte_identical_to_TASK011B=True)
    a7 = json.loads((TASK/'configs/arms/A5.json').read_text())
    a7.update(arm='A7',DEPTH_RELIABILITY_METHOD='UniformFromValidityAwareMax')
    dump(TASK/'configs/arms/A7.json',a7)
    dump(TASK/'configs/STAGE_CONTRACT.json',dict(
        stage='DATA_AUDIT_AND_CPU_ADMISSION_ONLY',GPU_runs_authorized_in_this_delivery=False,
        algorithms=['A0','A1','A4','A5','A7'],seeds=[43,44,45],maximum_future_plan=300,
        frames=64,stride=1,buffer=500,input_hw=[360,640],alpha=.01,
        GT_path_threshold_native_units=.0001,K_max_deviation_px=.001,
        mean_absolute_tolerance=1e-6,prior_precision='NATIVE_MOTION_FILTER_AUTOCAST_V2',
        sequence_exclusion='ALL historical comparative source sequences, including failed attempts and old stride4',
        source_comparison='A7 vs counterfactual A5 on the identical actual BA state',
        old_arm_config_hashes=configs,no_model_forward=True,no_remote_experiment=True))
    # Preserve the formal R2 YAML and precision protocol byte-for-byte. The
    # protocol's old progress counters are historical, never current status.
    for name in ('frozen_r2.yaml','VIPER_WINDOW_MANIFEST.csv'):
        shutil.copy2(inherited/'configs'/name,intake/('TASK011B_'+name))
    dump(intake/'START_RECEIPT.json',dict(parent_commit=PARENT,
        branch=git('branch','--show-current').decode().strip(),
        original_user_attachment_sha256=sha(attachment),
        models_loaded=0,CUDA_initializations=0,GPU_runs=0,
        inherited_files_verified=len(protected),local_original_files_protected=len(originals)))
    print(json.dumps(dict(status='CPU_STAGE_INITIALIZED',parent=PARENT,
        inherited_files=len(protected),baseline_files=len(originals))))


if __name__ == '__main__':
    main()
