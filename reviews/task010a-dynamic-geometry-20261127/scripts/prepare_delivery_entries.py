"""Final state/index entries from completed evidence; preserve existing index history."""
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def main():
    if not (TASK/'private/ANALYSIS_COMPLETE.json').exists():raise RuntimeError('Analysis still running')
    decision=json.loads((TASK/'08_reports/RESEARCH_DECISION.json').read_text())
    protection=json.loads((TASK/'09_reproducibility/ORIGINAL_ASSET_PROTECTION.json').read_text())
    if protection['status']!='PASS':raise RuntimeError('Historical protection failed')
    main=decision['primary'];state=main['decision'];candidate=main['method']
    test=(TASK/'private/cpu_tests_r5.log').read_text(encoding='utf-8',errors='replace')
    if 'Ran 30 tests' not in test or not test.rstrip().endswith('OK'):raise RuntimeError('Actual CPU test evidence unavailable')
    (TASK/'09_reproducibility/CPU_TEST_RESULTS.log').write_text(test,encoding='utf-8')
    (TASK/'09_reproducibility/CPU_TEST_REPORT.md').write_text('# CPU verification\n\n30/30 executed tests passed. The exact log is retained. They verify geometry/Schur algebra, actual adapter state preservation and scoring invariants on synthetic data; they do not establish segmentation/depth accuracy. The separate GPU offload/projection/fresh-context probe records remain distinct from CPU tests.\n',encoding='utf-8')
    shutil.copyfile(TASK/'07_cross_scene_evaluation/ALL_RUN_METRICS.csv',TASK/'08_reports/EXPERIMENT_TABLE.csv')
    rows=__import__('csv').DictReader((TASK/'07_cross_scene_evaluation/FROZEN_TRANSFER_WINDOW_TABLE.csv').open(encoding='utf-8'))
    rows=list(rows);lookup={(r['dataset'],r['method']):r for r in rows}
    failures=['# Recorded failures and accuracy regressions','',
        'No failed preparation is presented as a successful model/BA run. Original logs, empty pre-model output and explicit new attempt IDs are retained. See INTEGRATION_AUDIT and FINAL_REPORT for diagnosed preparation issues.','',
        '| Window | Method | Mean ATE | Baseline mean ATE | Reference unit |','|---|---|---:|---:|---|']
    for r in rows:
        if r['method']=='baseline':continue
        base=lookup[r['dataset'],'baseline'];key='sim3_ate_native_reference_units_mean'
        if float(r[key])>float(base[key]):failures.append(f"| {r['dataset']} | {r['method']} | {float(r[key]):.6f} | {float(base[key]):.6f} | {r['reference_unit']} |")
    failures += ['', 'These are completed-run accuracy regressions, not crashes. Every one remains in the primary tables. Missing motion/depth GT, forced keyframes, short windows, source-U coefficient/UBA-enable mismatch and offline future information remain research limits; no post-test tuning was performed.']
    (TASK/'08_reports/FAILURE_CASES.md').write_text('\n'.join(failures)+'\n',encoding='utf-8')
    (TASK/'00_project_audit/SOURCE_DIFF.md').write_text(f'''# Source / historical protection

The new worktree starts at `ff0c9ed761dbcdd6d2fe7b2cda5651c6e173efe1`. Changes are isolated Task010 scripts/tests/docs, generated review files and state indexes. No reset/clean/stash or original CUDA rebuild was performed.

Historical read-only checks: {protection['historical_pass_count']}/{protection['historical_file_count']} files match their saved bytes and SHA. Every successful native receipt uses the same tracker/extension identities. Upstream DROID-W reference is c3414af6047d06bafc1a6645d09f23247f3b2cdc; current workspace details and existing compatibility changes are explicit in ORIGINAL_ASSET_PROTECTION.json. A repository parent HEAD is never substituted for a nested snapshot's identity.

All five frozen transfer source hashes remain unchanged through evaluation. Publication uses an explicit isolated Git index and a new review branch; original worktree index/default branch/visibility are preserved.\n''',encoding='utf-8')
    (TASK/'00_project_audit/TASK008_TASK009_AUDIT.md').write_text('# TASK008 / TASK009 recovery\n\nOriginal Pi3MOS model fields, sealed Night cache, static-track cache, native source/weights and actual weight logs were read-only recovered. New same-state gate recalculation verifies first mean0.94646233 and117-call edge-weighted mean0.93998544. Source/target identities, optional native UBA, missing depth/confidence integration and all-stage scope are detailed in01_failure_diagnosis/FAILURE_ANALYSIS.md. Historical results are references, never merged with new scores.\n',encoding='utf-8')
    (TASK/'00_project_audit/EXECUTION_STATE.md').write_text(f'# Final execution state\n\nFixed experiment and analysis complete. Primary candidate `{candidate}`: `{state}`. 42 matched development +126 matched transfer runs, plus1 preliminary baseline, with all other preparation failures separately recorded. No next research stage or remote resource action is started. See08_reports/FINAL_REPORT.md and the published fixed-commit review.\n',encoding='utf-8')
    prefix=f'''<!-- TASK010A-20261127 -->
# TASK010-A · 2026-11-27

Status: **{state}**. Preselected candidate: `{candidate}`. 42 matched development and126 frozen cross-scene repetitions completed; four independent model providers on9windows. Bounded local32-frame protocol; no production baseline replacement or automatic next stage.

[Complete review](reviews/task010a-dynamic-geometry-20261127/FINAL_REVIEW.md) · [All tables and evidence](reviews/task010a-dynamic-geometry-20261127/) · [Review ZIP](review_packages/GAMECAM_TASK010A_REVIEW.zip) · [Full raw-array assets](https://github.com/Pseven0108/GameCam-VO/releases/tag/task010a-research-20261127)

---

'''
    for name in ['README.md','PROJECT_STATUS.md','REVIEW_INDEX.md']:
        p=ROOT/name;old=p.read_text(encoding='utf-8') if p.exists() else ''
        if '<!-- TASK010A-20261127 -->' in old:raise RuntimeError('Current task index already prepared; do not silently replace it')
        p.write_text(prefix+old,encoding='utf-8')
    print('Final delivery entries prepared from actual completed decision',state)


if __name__=='__main__':main()
