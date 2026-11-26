"""Prepare four consistent root entries in the isolated review publication."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='30c4149863ce202f4545a872707f0a6fc6a0bfb1'
SLUG=ROOT.name
ZIP='GAMECAM_TASK007D_METRIC_SCALE_PROVENANCE_REVIEW.zip'
source=json.loads((ROOT/'project_entries/BASE_ENTRIES.json').read_text('utf-8'))
assert source['base_commit']==BASE
body=f'''2026-11-26（Asia/Shanghai）。当前阶段：**TASK007D来源追溯完成；用途B（相对/辅助诊断），严格米制GT仍NO-GO**。

[最终评审](reviews/{SLUG}/FINAL_REVIEW.md) · [完整证据](reviews/{SLUG}) · [完整Review ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/{SLUG}/{ZIP})

- GitHub main完整可达历史26提交、6个CSV版本及3个UID已核查。2026-03-21新增484行Metric Scale列，其余字段未变；当前CSV与发布时字节一致。
- Reader只读取/应用尺度；未找到绑定三UID的生成程序、拟合帧、独立物理标尺或误差界。
- 作者旧的MoGe-2近似建议不能当作当前因子的生产事实；是否使用Metric3D或Test拟合仍未知。
- 不启动Metric3D Confidence校准/NLL/Coverage。模型运行0、GPU/CUDA0、新原始数据/权重下载0。
- TASK007A/B/C封存141项SHA通过；不改历史Release、VIPER主线或Baseline。
- VKITTI2训练家族重叠纠正继续有效；Scalix、CADP与Confidence-aware BA不启动。

完整历史入口保留在[上一固定提交](https://github.com/Pseven0108/GameCam-VO/tree/{BASE})。本次不自动进入下一阶段。
'''
titles={'README.md':'# GameCam-VO · TASK007D','PROJECT_STATUS.md':'# GameCam-VO 项目状态 · TASK007D',
        'REVIEW_INDEX.md':'# 当前评审：TASK007D','REVIEWING.md':'# 当前审查：TASK007D'}
plan=[]
for row in source['files']:
    name=row['path'];assert name in titles
    data=titles[name]+'\n\n'+body
    if name=='REVIEW_INDEX.md':
        old=row['content'];marker='## 历史索引：TASK007B'
        assert marker in old
        data+='\n---\n\n## 上一阶段：TASK007C\n\n'
        data+=f'[TASK007C原始评审](https://github.com/Pseven0108/GameCam-VO/blob/{BASE}/reviews/task007c-omniworld-metric-gt-admission-overlap-20261126/FINAL_REVIEW.md) · [原始完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007c-omniworld-metric-gt-admission-overlap-20261126/GAMECAM_TASK007C_OMNIWORLD_METRIC_GT_ADMISSION_REVIEW.zip)\n\n'
        data+='---\n\n'+old[old.index(marker):]
    elif name=='REVIEWING.md':
        data+='\n审查重点：首次发布与实际生成的区别；484行非尺度字段保持一致；MoGe-2建议未连接到CSV；独立标尺缺失；Test拟合未知；OpenReview访问边界；B类用途不代表严格GT准入。\n'
    target=ROOT/'project_entries'/name
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(data)
    plan.append({'path':name,'base_ref':BASE,'base_git_blob_sha':row['sha'],'source_file':target.relative_to(ROOT).as_posix(),
                 'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
with (ROOT/'project_entries/ENTRY_UPDATE_PLAN.json').open('x',encoding='utf-8') as f:
    json.dump({'base_commit':BASE,'scope':'New review branch/commit only; preserve visibility/default branch and all sealed history','files':plan},f,indent=2);f.write('\n')
print('Prepared4 consistent state entries; no local tracked root or baseline overwritten.')
