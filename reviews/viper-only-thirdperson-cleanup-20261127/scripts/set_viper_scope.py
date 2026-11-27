"""Set current research direction without editing frozen experiment protocols."""
from pathlib import Path
import hashlib,json

OUT=Path(__file__).resolve().parent
roots=[Path('D:/aaa/GameCam-VO'),Path('D:/aaa/GameCam-VO-TASK009'),Path('D:/aaa/GameCam-VO-TASK010-A')]
marker='<!-- VIPER_ONLY_CURRENT_SCOPE_20261127 -->'
scope='''## Current research scope — user instruction, 2026-11-27

VIPER is the sole active experimental dataset. The user has abandoned the early third-person research direction and explicitly requested removal of its datasets and early experiments: WildWorld, OmniWorld-Game, DigiDogs and GameVerse. Do not resume, redownload or extend those retired branches automatically.

Old chat messages, historical commits, reviews and prior memory references about a third-person/WildWorld/OmniWorld mainline are historical context, not the current research plan. Do not infer a new task or dataset from them. Use the user's latest VIPER task and its approved frozen protocol. Keep existing VIPER data/results, shared baseline code/weights and environments protected. Real reference assets are retained but are not an authorization for new non-VIPER experiments. No new GPU run is authorized by this cleanup.
'''
status={'date':'2026-11-27 Asia/Shanghai','active_dataset':'VIPER','current_direction':'DROID-W_BASELINE_OPTIMIZATION_ON_VIPER','retired_third_person_branches':['WildWorld','OmniWorld-Game','DigiDogs','GameVerse'],'third_person_experiments_auto_resume_allowed':False,'current_experiment_running':False,'latest_completed_task':'TASK010-A','latest_task_decision':'NO_GO_FOR_GENERALIZED_IMPROVEMENT','historical_GitHub_commits_are_not_current_instructions':True,'cleanup_evidence':'D:/aaa/maintenance/VIPER_ONLY_THIRDPERSON_CLEANUP_20261127','no_new_algorithm_or_GPU_experiment_authorized':True}
records=[]
def write(p,text):
    old=p.read_bytes() if p.exists() else None
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    records.append({'path':str(p),'sha256_before':hashlib.sha256(old).hexdigest() if old is not None else None,'sha256_after':hashlib.sha256(p.read_bytes()).hexdigest()})
header=f'''{marker}
# 当前实验主线：VIPER

2026-11-27，用户明确决定：停止早期第三人称方向，清理 WildWorld、OmniWorld-Game、DigiDogs、GameVerse 数据和早期实验。后续仅按 VIPER 的最新授权任务继续 DROID-W 优化，不从旧聊天、旧报告或历史提交自动恢复第三人称任务。

TASK010-A 已完成，结论为 `NO_GO_FOR_GENERALIZED_IMPROVEMENT`；尚无被接受的通用改进方案。保持现有 VIPER Baseline 与冻结评价协议。本次是清理和方向更新，不启动新实验。

详见 [当前范围](CURRENT_RESEARCH_SCOPE.json) 与 [清理记录](reviews/viper-only-thirdperson-cleanup-20261127/FINAL_REVIEW.md)。

---

'''
for root in roots:
    p=root/'AGENTS.md';text=p.read_text(encoding='utf-8') if p.exists() else ''
    if marker not in text:write(p,marker+'\n'+scope+'\n'+text)
    write(root/'CURRENT_RESEARCH_SCOPE.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    write(root/'RESEARCH_DIRECTION_CURRENT.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    write(root/'CURRENT_RESEARCH_STATUS.md',header)
    for name in ['README.md','PROJECT_STATUS.md','REVIEW_INDEX.md']:
        p=root/name;old=p.read_text(encoding='utf-8') if p.exists() else ''
        if marker not in old:write(p,header+old)
    p=root/'configs/dataset.yaml'
    if p.exists():
        old=p.read_text(encoding='utf-8')
        if 'dataset: WildWorld' in old:
            write(p,'# Current dataset: VIPER. Use the frozen VIPER manifests and dedicated pipelines.\n# The legacy generic inspector has no data roots; retired third-person inputs must not be restored.\n'+old.replace('dataset: WildWorld','dataset: VIPER',1))
    p=root/'docs/LOCAL_EXPERIMENT_WORKFLOW.md'
    if p.exists():
        old=p.read_text(encoding='utf-8')
        if marker not in old:write(p,marker+'\n'+scope+'\n---\n\n'+old)
(OUT/'CURRENT_SCOPE_FILE_UPDATES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
notes=Path('C:/Users/Administrator/.codex/memories_v2/extensions/ad_hoc/notes')
notes.mkdir(parents=True,exist_ok=True)
note=notes/'20261127-gamecam-viper-only-retire-thirdperson.md'
note.write_text('''# Explicit user correction — GameCam-VO, 2026-11-27

The user has changed the experimental direction to VIPER, and explicitly requests deletion of third-person datasets and the earliest third-person experiments so they do not steer Codex memory or future work. VIPER is the sole active experimental dataset. Retire the WildWorld / OmniWorld-Game / DigiDogs / GameVerse third-person research direction. Earlier notes/chat/commits describing WildWorld or third-person as the mainline are superseded historical context. Do not proactively retrieve old third-person studies to define the current plan, resume them, redownload their data, or propose further third-person experiments. Use latest VIPER-specific user instructions and keep existing VIPER baseline data, model weights, code, environments and approved protocols intact. Historical GitHub releases and chat history are not rewritten by local filesystem cleanup. This correction does not authorize a new algorithm stage or GPU run.
''',encoding='utf-8')
print('VIPER-only scope applied to',len(roots),'project workspaces;',len(records),'current metadata documents updated. Explicit user memory correction saved.')
