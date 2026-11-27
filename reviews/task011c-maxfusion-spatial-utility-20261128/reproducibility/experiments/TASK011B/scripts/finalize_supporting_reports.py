"""Replace unpublished historical checkpoint pointers with actual final evidence.

No runtime source/configuration is edited and no model is launched. The former
CPU-only checkpoint is retained under an explicitly historical review folder.
"""
import csv,json,re,shutil
from pathlib import Path
from common import ROOT,TASK,dump,sha

REVIEW=ROOT/'reviews/task011b-validity-aware-cadp-dr-20261127'


def write(relative,text):
    path=REVIEW/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.strip()+'\n',encoding='utf-8')


def historical(relative):
    source=REVIEW/relative
    dest=REVIEW/'09_LOGS/HISTORICAL_CPU_BLOCKED_CHECKPOINT'/relative
    if source.exists() and not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)


def main():
    decision=json.loads((REVIEW/'10_FINAL_REPORT/TASK011B_DECISION.json').read_text())
    audit=json.loads((TASK/'evaluation/FORMAL_RUN_CONTRACT_AUDIT.json').read_text())
    protection=json.loads((TASK/'intake/FINAL_ORIGINAL_ASSET_PROTECTION.json').read_text())
    qa=json.loads((TASK/'private/FINAL_FIGURE_QA.json').read_text())
    if decision['formal_window_runs']!=140 or audit['status']!='PASS_COMPLETE' or protection['status']!='PASS':
        raise RuntimeError('Final actual batch/source protection evidence is incomplete')
    if qa['status']!='PASS_ACTUAL_FINAL_FIGURES' or not qa['actual_final_batch_complete']:
        raise RuntimeError('Inspect the final figures before completing the QA report')
    tests=(TASK/'private/CPU_TESTS_FINAL.log').read_text(encoding='utf-8-sig')
    match=re.search(r'Ran (\d+) tests',tests)
    if not match or not tests.rstrip().endswith('OK'):
        raise RuntimeError('Final CPU test output is not a real passing run')
    count=int(match.group(1))
    replay=json.loads((TASK/'runs/cpu_003/ARTIFACT_REPLAY_VERIFICATION.json').read_text())
    if replay['status']!='PASS':raise RuntimeError('Actual cached-array replay is missing')
    resources=json.loads((TASK/'evaluation/RESOURCE_SAMPLE_COVERAGE.json').read_text())
    replacement=(
        '04_R3_VIPER_EVALUATION/R3_INPUT_ADMISSION.md',
        '08_TESTS/CPU_TEST_REPORT.md','09_LOGS/ISSUES_AND_CORRECTIONS.md',
        '10_FINAL_REPORT/GPU_RESOURCE_BLOCKER.md',
        '10_FINAL_REPORT/STORAGE_AND_RESUMPTION.md','06_FIGURES/FIGURE_QA.md')
    for name in replacement:historical(name)
    initial='10_FINAL_REPORT/ORIGINAL_ASSET_PROTECTION.json'
    historical(initial)
    initial_value=json.loads((REVIEW/initial).read_text())
    initial_value.update(audit_phase='HISTORICAL_INITIAL_CPU_CHECKPOINT_READ_ONLY_VERIFICATION',
                         GPU_or_model_runs_field_counts_this_initial_audit_only=True,
                         final_asset_protection='09_LOGS/FINAL_ORIGINAL_ASSET_PROTECTION.json',
                         actual_final_formal_outcomes=140)
    dump(REVIEW/initial,initial_value)
    dump(REVIEW/'07_CONFIGS/ACTUAL_RUNTIME_RESOLUTION.json',dict(
        status='COMPLETED_ACTUAL_140_FORMAL_OUTCOMES',
        initial_protocol_file='R2_R3_EXECUTION_PROTOCOL.json',
        initial_protocol_status_is_historical=True,initial_actual_window_runs_is_historical=True,
        scientific_frozen_configuration_not_changed=True,formal_window_runs=140,
        formal_precision='NATIVE_MOTION_FILTER_AUTOCAST_V2',
        source_receipts='04_R3_VIPER_EVALUATION/R3_EXECUTION_LEDGER.csv',
        actual_contract_audit='04_R3_VIPER_EVALUATION/FORMAL_RUN_CONTRACT_AUDIT.json',
        formal_run_sources=audit['common_runtime_source_sha256'],
        live_first_frame_native_cache_checks=20,
        original_protected_assets='09_LOGS/FINAL_ORIGINAL_ASSET_PROTECTION.json',
        runtime_configuration_modified_during_batch=False))
    write('04_R3_VIPER_EVALUATION/R3_INPUT_ADMISSION.md',f'''# Final actual input and execution admission

All140 planned formal outcomes have been collected and reverified; {decision['complete_64_frame_trajectories']} contain64 valid frame poses, {decision['algorithm_failures']} retain an algorithm failure.

The preselected20 windows come from20 distinct Validation sequences,4 per weather. The exact manifest was frozen before method outcomes. All1280 input JPEGs passed member CRC and complete decode. RGB IDs remain original; Camera ID=RGB ID−1 is checked against the existing camera records. Constant-K admission uses the original maximum0.001px threshold; variable-K042/043 are excluded rather than repaired selectively.

GT is read by the local offline evaluator only and is absent from GPU_RGB_INPUTS.json. The formal source/configuration identity audit is FORMAL_RUN_CONTRACT_AUDIT.json; each archive's original internal SHA is rechecked, rather than relying solely on its earlier transfer receipt.

All20 A0 live cache checks passed exact nativeAMP depth identity and unchanged CPU/CUDA RNG. A0/A1 remain the original and isolated D1 endpoint controls, not a fabricated D0 reference. The10 old FP32 protocol pilots are retained under explicitly excluded engineering evidence.

The original R2_R3_EXECUTION_PROTOCOL.json includes its initial GPU-unavailable/zero-run metadata and is preserved as a design snapshot. Read07_CONFIGS/ACTUAL_RUNTIME_RESOLUTION.json and the actual run ledger for final execution state. No runtime scientific setting was changed to improve scores.
''')
    write('08_TESTS/CPU_TEST_REPORT.md',f'''# Final actual verification

{count}/{count} CPU tests passed in CPU_TESTS_FINAL.log. The original intermediate logs are retained separately; their63/66 counts describe those earlier source revisions, not this final run.

Coverage includes numerical validity, bounded/symmetric TTA, undefined values versus rejection, Native fallback, all risk maps, D0/D1/fractional depth algebra, gradient sign, block/full covariance, geometry separation, stage boundaries, unchanged native kernel/U bodies, real-context regression receipts, and aligned-orientation trajectory evaluation.

The existing cached-array replay passed528 arrays,240 metric rows and3360 scalar values with max absolute difference0. It preserves the7 diagnostic zero predictions; it is an auxiliary reused-data check, not independent GT admission.

Actual nativeGPU evidence is separate: a real first-Local-BA D0/D1 paired regression passed the prespecified mixed tolerance with two native iterations and U updates. All140 formal execution contracts passed; this does not assert global native bitwise determinism. The20 live A0 cache identity checks passed. Original historical assets and original weights/extension were rehashed after the batch.

Full original arrays, CPU outputs, real regression inputs/outputs and runtime logs are included or explicitly linked by sourceSHA. Tests reading the original frozen source or camera data require those permitted external assets; the saved-array replay is the standalone CPU evidence check.
''')
    write('09_LOGS/ISSUES_AND_CORRECTIONS.md','''# Actual engineering issues and corrections

The initial CPU-only/GPU-unavailable checkpoint was never a completed downstream experiment. Its original reports are retained in HISTORICAL_CPU_BLOCKED_CHECKPOINT with historical labels. The final140 outcomes and numerical evidence supersede its current-status pointers only.

Early installation/launch attempts encountered offline model-cache resolution, spawn/Printer context and disk admission problems. Their diagnostics and partial evidence are retained. The installed original baseline and weights were not replaced. A unique candidate module and independent namespace were used.

The first10 completed engineering window pilots omitted MotionFilter's native CUDA autocast and initially preprocessed onCUDA. A real same-frame diagnostic found maxabs12.228088 and206138/230400 differing depth pixels versus nativeAMP. All10 were excluded from formal estimates before the corrected fixed batch; their source revisions, receipts and metrics remain in09_LOGS/EXCLUDED_FP32_PILOT_* and native diagnostics. Formal preprocessing runs onCPU, and the original no_grad/CUDA-autocast predictor path is retained. Every A0 window recomputes its first frame and checks exact cache equality and unchanged RNG.

The final evaluator rotates trajectory orientations by the same fitted global rotation as positions when reporting Sim3-aligned RPE. Known-transform CPU tests cover this behavior. The original camera GT and metric implementation remain preserved.

No selective windows, GT-fitted risk thresholds, retries after native failures, best-seed selection or failure deletion was used to make a method appear better. Algorithm failures remain in all140 completion denominators; paired accuracy tables show the available-pair N explicitly.
''')
    write('10_FINAL_REPORT/GPU_RESOURCE_BLOCKER.md','''# Historical GPU blocker — resolved for this batch

This is not a current blocker. The user subsequently supplied the allocated RTX3090 endpoint and the140 formal outcomes are complete. The earlier GPU-unavailable report is preserved under09_LOGS/HISTORICAL_CPU_BLOCKED_CHECKPOINT/10_FINAL_REPORT/GPU_RESOURCE_BLOCKER.md.

The machine was not rebooted, shut down or reallocated by this task. The preexisting driver-reported allocation was retained; device-total memory samples include it. Read the actual resource coverage and per-run child peaks instead of inferring24GB of exclusive free VRAM.
''')
    write('10_FINAL_REPORT/STORAGE_AND_RESUMPTION.md',f'''# Final storage and lifecycle status

All140 planned formal outcomes were archived to localD:, checked by whole-archiveSHA and original internalSHA, then rechecked during final execution audit. Only newly created task outputs/transfer duplicates were released remotely after identity/open-file checks; no historical result or weight was deleted.

Each job is admitted with the10GiB safety reserve plus600MiB working allowance. The original per-job runtime receipts and sampled disk-free values are retained. Disk capacity and peak memory are measurements with the stated sampling limitations, not nominal-capacity estimates.

Resource sampler: {resources['samples']} reads, {resources['failed_sample_reads']} failed reads; {len(resources['unmeasured_window_jobs'])} window jobs have no sample. Missing jobs are explicitly listed in RESOURCE_SAMPLE_COVERAGE.json. The20-second samples are lower bounds on true peaks and do not replace tracking-child PyTorch allocator peaks.

Full original run/cache archives remain under experiments/TASK011B/gpu_results onD:. Public reviews omit rawRGB, weights and embedded-RGB native videos; exact BA-grid numerical states and coefficients plus complete trajectories/logs are public. This distinction is recorded in derivation manifests.

The formal task is complete and awaiting review; no automatic next stage or GPU retry is scheduled. After verified publication, only the just-delivered local completeReviewZIP copies may be deleted under the user's standing instruction. Expanded files, code, full evidence and datasets remain. No shutdown is authorized for this task.
''')
    pngs=sorted((REVIEW/'06_FIGURES').rglob('*.png'))
    svgs=sorted((REVIEW/'06_FIGURES').rglob('*.svg'))
    pdfs=sorted((REVIEW/'06_FIGURES').rglob('*.pdf'))
    write('06_FIGURES/FIGURE_QA.md',f'''# Actual final figure verification

{len(pngs)} PNG, {len(svgs)} editableSVG and {len(pdfs)} PDF files. CPU R0/R1 auxiliary-ranking/validity plots and actual R3 trajectory plots are separate evidence populations. No synthetic VO result is drawn.

Final human-visible inspection record: FINAL_FIGURE_QA.json, including image identities. The batch-complete results were plotted before final inspection. Method/weather colors and directions are fixed. Weather cells use actual denominators and0..1 completion scale; undefined scores showNA. Paired differences show source-sequence bootstrap intervals with N, not BA-event/pixel replicates. Trajectory panels share one global alignment per displayed full window, not per-segment scale fitting.

R0/R1 contacts retain the original image content and mark invalid pixels; display clipping does not alter saved numbers. R3 rawscale, single-global-Sim3 accuracy, runtime and completion are reported separately. Device sample lower bounds and child allocator peaks are not conflated. Negative outcomes are retained.

This is research-review figure QA, not a journal-specific submission certificate.
''')
    shutil.copy2(TASK/'private/FINAL_FIGURE_QA.json',REVIEW/'06_FIGURES/FINAL_FIGURE_QA.json')
    shutil.copy2(TASK/'private/CPU_TESTS_FINAL.log',REVIEW/'08_TESTS/CPU_TESTS_FINAL.log')
    # This explicit overlay keeps the initial immutable protocol honest without
    # touching the config/source currently used by the completed remote jobs.
    write('07_CONFIGS/README.md','''# Frozen design and actual execution

R2_R3_EXECUTION_PROTOCOL.json is the initial frozen design snapshot. Its GPU-unavailable,0-run and unverified-draft status fields are historical metadata, not the final runtime state. Its scientific settings remain unchanged.

ACTUAL_RUNTIME_RESOLUTION.json links the final140-outcome execution ledger, nativeAMP precision contract, live-cache checks and original-asset protection. Actual per-run native_config.yaml and sourceSHA receipts are in04_R3_VIPER_EVALUATION/evidence/windows. The separately named10 FP32 engineering pilots are excluded from all formal estimates.
''')
    write('04_R3_VIPER_EVALUATION/evidence/NUMERICAL_EVIDENCE_SCHEMA.md','''# Public numerical evidence and exact coefficient interpretation

The complete original archives remain on the user's D: and are linked by whole/archive and member SHA. This public evidence is a documented exact selection of numerical fields, not a substitute containing recoverable raw RGB or full original video archives.

## Prior-cache grids

Each `priors/cache_<window>/<input-index>.npz` uses exactly y=3+8n, x=3+8n (45x80), matching the native disparity grid. Depth/confidence/validity values are selected directly, without interpolation. `flip_depth_aligned` and `flip_confidence_aligned` are unflipped into the native image coordinates. Full360x640 rankings are computed before grid selection; ranking only the published grid would not reproduce the actual controller.

`coefficient_A0` and `coefficient_A1` are the unit endpoint strengths. `coefficient_A2` through `coefficient_A5` are the exact float32 per-pixel reliability strengths supplied to the candidate. **`coefficient_A6` is the reliability r before geometry multiplication, not the final s=g*r.** Its r equals A4's rule at the same timestamp. The geometry multiplier is recomputed from each evolving A6 BA state and each internal iteration, so it cannot be represented as a single per-input-frame cache field.

## A6 geometry and effective prior

The original per-call `native_ba_calls.jsonl` contains `geometry_trace[iteration][active-source-row][field]`. The four fields are [g, u, positive-disparity valid-pixel count, native video slot kx]. The fourth field identifies the source slot explicitly; `keyframe_input_indices[slot]` maps that slot to the input timestamp and prior-cache file. `active_source_indices` is also retained. Two native internal iterations are preserved. For each matching source/iteration, the pixel strength is s=g*r. The native prior mask m is then applied to the curvature/gradient formulas. `effective_prior_mean_by_iteration` records the actual mask-weighted mean; it is not an independently calibrated depth probability.

## Final keyframe states and trajectories

`keyframe_state_ba_grid.npz` preserves native timestamps, poses/tum_poses, intrinsics, droid_disps and uncertainties; mono_disps is selected at the same exact native grid. These are final saved keyframe states, not all pre-BA intermediate tensors. Each original BA log retains the stated update/geometry/U summaries; full per-event residuals, Jacobians and complete state tensors were not exported and cannot be inferred from these summaries.

`trajectory.npz` contains64 original RGB IDs and their final exported c2w poses for a complete run. `initialization_partial.npz` is a genuine incomplete initialization state and must not be treated as a complete trajectory or filled by interpolation. The full140 outcome denominator is preserved. No model weight, raw dataset image or environment binary is included.
''')
    print('FINAL_SUPPORTING_REPORTS_ACTUAL',count,len(pngs),len(svgs),len(pdfs),flush=True)


if __name__=='__main__':main()
