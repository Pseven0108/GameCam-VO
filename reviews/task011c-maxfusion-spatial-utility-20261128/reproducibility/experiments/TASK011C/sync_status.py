"""Update current-stage entry points; preserve previous scientific records."""
import json
from pathlib import Path
import shutil

from common import BASE,REVIEW,REVIEW_REL,ROOT,TASK,dump


def main():
    link = f'{REVIEW_REL}/FINAL_REVIEW.md'
    status = f'''# GameCam-VO — TASK011C CPU complete / data admission blocked

2026-11-28, Asia/Shanghai. VIPER is the sole active experimental dataset.

TASK011C A7 implementation and 122 CPU tests passed. Strict source exclusion
leaves 0/47 Validation sequences eligible; Rain also has only 3 remaining if
excluding TASK011B alone. No GPU pilot, model forward or formal run started.
Research decision: INCONCLUSIVE. Stop for review and a data-protocol decision.

[Current complete review]({link}).

TASK011B remains sealed: 140 formal outcomes, 98 complete trajectories and
42 initialization failures; it is historical evidence, not TASK011C results.
Production baseline/weights and all existing scientific results are preserved.
'''
    index_line = f'- [TASK011C data audit + A7 CPU readiness — INCONCLUSIVE, GPU=0]({link})\n'
    for root in (ROOT,BASE):
        for name in ('PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md'):
            path = root/name
            old = path.read_text(encoding='utf-8') if path.exists() else ''
            if 'TASK011C CPU complete / data admission blocked' not in old:
                path.write_text(status.strip()+'\n\n---\n\n## Archived previous status\n\n'+old,encoding='utf-8')
        path = root/'REVIEW_INDEX.md'
        old = path.read_text(encoding='utf-8') if path.exists() else '# Current reviews\n'
        if index_line.strip() not in old:
            path.write_text('# Current reviews\n\n'+index_line+'\n'+old.removeprefix('# Current reviews').lstrip(),encoding='utf-8')
        for name in ('CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json'):
            path = root/name
            old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            old.update(date='2026-11-28 Asia/Shanghai',active_dataset='VIPER',current_task='TASK011C',
                current_status='CPU_PASSED_DATA_ADMISSION_BLOCKED',latest_completed_task='TASK011B',
                current_experiment_running=False,review=link,formal_window_runs=0,
                complete_trajectories=0,eligible_new_sequences=0,
                TASK011B_historical_formal_outcomes=140,TASK011B_historical_complete_trajectories=98,
                no_automatic_third_person_resume=True,next_stage_started=False)
            dump(path,old)
    # Only this new review is mirrored into the canonical project entry point.
    canonical = BASE/REVIEW_REL
    if canonical.exists():
        raise FileExistsError('Do not overwrite an earlier canonical TASK011C review')
    shutil.copytree(REVIEW,canonical)
    path = ROOT/'README.md'
    old = path.read_text(encoding='utf-8')
    banner = f'''<!-- TASK011C_CURRENT_START -->
# Current: TASK011C data audit and A7 CPU verification

**CPU PASS; DATA BLOCKED; INCONCLUSIVE. GPU=0.**

[Complete current review]({link}). 122 CPU tests passed. All 47 Validation source
sequences have historical comparative exposure; the requested new 20-sequence
sample cannot be admitted. No formal GPU run, new model or baseline modification.
Do not interpret historical TASK011B results below as TASK011C evidence.
<!-- TASK011C_CURRENT_END -->

'''
    if '<!-- TASK011C_CURRENT_START -->' not in old:
        path.write_text(banner+old,encoding='utf-8')
    print('CURRENT_STATE_UPDATED_WITH_HISTORY_PRESERVED')


if __name__ == '__main__':
    main()
