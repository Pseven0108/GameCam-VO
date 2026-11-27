"""Reuse the authorized release channel, with this stage's explicit scope."""
import ast,json,shutil
from pathlib import Path
from common import BASE,PARENT,REVIEW,REVIEW_REL,ROOT,TASK,csvwrite,dump,sha

def main():
    decision=json.loads((REVIEW/'TASK011D_DECISION.json').read_text());total=decision['tests_passed']
    old=ROOT/'experiments/TASK011C'
    source=(old/'publish_review.py').read_text(encoding='utf-8')
    source=source.replace('TASK011C','TASK011D').replace('task011c','task011d')
    source=source.replace("git('--literal-pathspecs','add','-f'","git('--literal-pathspecs','add','--sparse','-f'")
    start=source.index("        message.write_text(");end=source.index("        git('commit'",start)
    source=source[:start]+f"        message.write_text('TASK011D: source-only A7 GPU adapter and Route A dual-validation preparation\\n\\n{total} tests pass; 1216 RGB audited; no formal SLAM or native BA.\\n',encoding='utf-8')\n"+source[end:]
    source=source.replace("name='TASK011D — A7 CPU readiness and Validation source admission'","name='TASK011D — A7 GPU Adapter and dual-validation preparation'")
    source=source.replace("body='CPU preparation passed; data admission blocked. No GPU results. Full evidence upload in progress.'",
        "body='Preparation passed; local synthetic CUDA only. No formal SLAM results. Full evidence upload in progress.'")
    start=source.index("    body = f'''TASK011D first-stage complete:");end=source.index("    if release['draft']:",start)
    body="""    body = f'''TASK011D preparation complete: source-only A7 GPU adapter, 19 Route A windows, separate fixed-state and end-to-end frameworks.

**169/169 tests passed. 1216 JPEGs fully decoded/CRC-verified.** Local RTX5060 synthetic CUDA only; remote frozen PyTorch2.1 CPU API compatibility checked without CUDA initialization. No model inference, native BA, pilot or formal SLAM runs.

285 future E2E jobs and the fixed-state protocol are frozen for review. Historical full-sequence baseline exposure is explicitly marked; TASK011B sources and val_014 are excluded. Secondary degradation margins remain proposals awaiting approval.

- [Fixed-commit final review](https://github.com/{REPO}/blob/{commit}/{manifest['review_directory']}/FINAL_REVIEW.md)
- [Complete expanded evidence](https://github.com/{REPO}/tree/{commit}/{manifest['review_directory']})
- [ZIP SHA256](https://github.com/{REPO}/blob/{commit}/review_packages/{paths[1].name})

Full ZIP includes source, all final and development test logs, profiler traces, transfer/performance evidence, data admission metadata, configuration/implementation hashes and both experiment protocols. Raw RGB/GT, weights, environments and native binaries are excluded. Original evidence stays local.

This is engineering/data readiness, not evidence that A5 beats A7. Formal GPU execution requires separate approval. No production baseline or sealed B/C release changed.
'''
""".replace('169/169',f'{total}/{total}')
    source=source[:start]+body+source[end:]
    source=source.replace('GPU_runs=0,models_loaded=0,CUDA_initialized=False',
        'formal_SLAM_runs=0,models_loaded=0,formal_SLAM_GPU_started=False,synthetic_CUDA_executed=True')
    ast.parse(source);(TASK/'publish_review.py').write_text(source,encoding='utf-8')
    source=(old/'package_review.py').read_text(encoding='utf-8').replace('task011c-maxfusion-spatial-utility-20261128','task011d-a7-gpu-adapter-dual-validation-20261128')
    source=source.replace('GAMECAM_TASK011C_MAXFUSION_SPATIAL_UTILITY_REVIEW.zip','GAMECAM_TASK011D_A7_GPU_ADAPTER_DUAL_VALIDATION_REVIEW.zip')
    source=source.replace("branch='task011d-a7-gpu-adapter-dual-validation-20261128'","branch='codex/task011d-a7-gpu-adapter-dual-validation-20261128'")
    ast.parse(source);(TASK/'package_review.py').write_text(source,encoding='utf-8')
    readme='''# TASK011D — source-only GPU Adapter and dual validation

Preparation only: local synthetic CUDA tests, Route A data admission and two independent frameworks.
No research models, native BA, Pilot or 285 formal jobs ran.

- `uniform_control.py`: source-only GPU math and compact D2H logging.
- `reports/TRANSFER_AUDIT.json` and `PERFORMANCE_PROFILE.json`: measured evidence.
- `data/`: 19 windows and 1216 image/camera admission records, historical exposure explicit.
- `collect_snapshots.py` / `fixed_state_replay.py`: complete A0 inputs and independent A5/A7/A5 branches.
- `run_end_to_end.py`: default validate-only; approved serial independent 285-job path.
- `score_completed_runs.py` / `analyze_results.py`: offline scoring, explicit failure counts, sequence bootstrap.
- `configs/IMPLEMENTATION_LOCK.json`: reviewed code hashes.

Use the existing `D:/aaa/envs/gamecam-vo/python.exe`. Synthetic CUDA is tested on local RTX5060.
Formal native runners are for the approved Linux3090 environment and are gated before model imports.

CPU tests: `python -m unittest discover -s experiments/TASK011D/tests -p test_framework_cpu.py -v`.
CUDA contracts: `python -m unittest discover -s experiments/TASK011D/tests -p test_uniform_cuda.py -v`.
Transfer contracts: `python -m unittest discover -s experiments/TASK011D/tests -p test_no_full_buffer_d2h.py -v`.
Preserve the B/C sibling source trees in this review's reproducibility folder; they are immutable dependencies.

Default safe CLI: `python experiments/TASK011D/run_end_to_end.py`.
FSR default safe CLI: `python experiments/TASK011D/fixed_state_replay.py`.
No approved runtime file is included. Synthetic test fixtures are not experimental outcomes.
'''
    (TASK/'README.md').write_text(readme,encoding='utf-8')
    status=f'''# GameCam-VO — TASK011D preparation complete, review required

2026-11-28, Asia/Shanghai. VIPER remains the only active dataset.

TASK011D: source-only A7 adapter fixed; {total} tests passed. Route A19 windows and1216 JPEGs
passed real data admission, explicitly historically exposed. FSR/E2E protocols and285-job order frozen.
Local synthetic CUDA only; formal SLAM/native BA/Pilot/model forwards all0. Secondary margins await approval.

[Complete current review]({REVIEW_REL}/FINAL_REVIEW.md).

The current readiness claim does not establish A5>A7. Do not launch formal models without subsequent approval.
TASK011B/C are sealed history. TASK011C's strict-data blocker is amended for this new Route A only.
'''
    for root in (ROOT,BASE):
        for name in ('PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md'):
            p=root/name;oldtext=p.read_text(encoding='utf-8') if p.exists() else ''
            if 'TASK011D preparation complete' not in oldtext:p.write_text(status+'\n---\n\n## Previous status — archived\n\n'+oldtext,encoding='utf-8')
        p=root/'REVIEW_INDEX.md';oldtext=p.read_text(encoding='utf-8') if p.exists() else ''
        item=f'- [TASK011D complete preparation review — {total} tests, 19 windows, formal SLAM=0]({REVIEW_REL}/FINAL_REVIEW.md)'
        if item not in oldtext:p.write_text('# Current reviews\n\n'+item+'\n\n'+oldtext.removeprefix('# Current reviews').lstrip(),encoding='utf-8')
        for name in ('CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json'):
            p=root/name;x=json.loads(p.read_text()) if p.exists() else {}
            x.update(date='2026-11-28 Asia/Shanghai',active_dataset='VIPER',current_task='TASK011D',
                current_status='PREPARATION_COMPLETE_WAITING_REVIEW',current_experiment_running=False,
                latest_completed_preparation='TASK011D',latest_completed_formal_experiment='TASK011B',
                review=REVIEW_REL+'/FINAL_REVIEW.md',route='A',selected_windows=19,tests_passed=total,
                formal_window_runs=0,complete_trajectories=0,synthetic_CUDA_executed=True,
                eligible_new_sequences='not a blind/unseen-sequence study',historical_baseline_exposure=True,
                secondary_thresholds_approved=False,next_stage_started=False)
            dump(p,x)
    p=ROOT/'README.md';oldtext=p.read_text(encoding='utf-8')
    p.write_text(status+'\n---\n\n## Previous overview — archived\n\n'+oldtext,encoding='utf-8')
    # Mirror final current-stage code first, then compute the task manifest.
    for p in sorted(TASK.rglob('*')):
        if not p.is_file() or any(v in p.parts for v in ('private','__pycache__','fixed_state','runs','cache','execution_ledger')):continue
        if p.name=='SHA256_MANIFEST.csv' or p.suffix in ('.pt','.npz','.npy','.jpg','.jpeg','.pyc'):continue
        copy_to=REVIEW/'reproducibility/experiments/TASK011D'/p.relative_to(TASK)
        copy_to.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,copy_to)
    paths=[p for p in sorted(TASK.rglob('*')) if p.is_file() and not any(v in p.parts for v in ('private','__pycache__','fixed_state','runs','cache','execution_ledger')) and p.name!='SHA256_MANIFEST.csv']
    csvwrite(TASK/'SHA256_MANIFEST.csv',[dict(path=p.relative_to(TASK).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in paths])
    shutil.copy2(TASK/'SHA256_MANIFEST.csv',REVIEW/'reproducibility/experiments/TASK011D/SHA256_MANIFEST.csv')
    canonical=BASE/REVIEW_REL
    if canonical.exists():raise FileExistsError('Preserve previous canonical delivery')
    shutil.copytree(REVIEW,canonical)
    print('DELIVERY_AND_EXPLICIT_PUBLISHER_PREPARED',total)

if __name__=='__main__':main()
