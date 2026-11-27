"""Stage a full audit artifact, keeping original datasets/weights out of Git."""
from common import *
import shutil,subprocess

REVIEW=ROOT/'reviews/task011a-depth-reliability-fusion-20261127'
TAG='task011a-depth-reliability-fusion-20261127'
MARKER='<!-- TASK011A-20261127 -->'

def main():
    run=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path'])
    if REVIEW.exists():raise RuntimeError('Do not overwrite an existing review stage')
    if not (TASK/'private/FINAL_EVIDENCE_READY.json').exists():raise RuntimeError('Final evidence check required')
    REVIEW.mkdir(parents=True)
    for p in (TASK/'reports').iterdir():
        if p.is_file():shutil.copyfile(p,REVIEW/p.name)
    shutil.copyfile(TASK/'reports/TASK011A_FINAL_RESEARCH_REPORT.md',REVIEW/'FINAL_REVIEW.md')
    for source,name in [(TASK/'scripts','code'),(TASK/'tests','tests'),(TASK/'intake','intake'),(TASK/'figures','figures'),(run,'results')]:
        target=REVIEW/name;target.mkdir()
        for p in source.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                out=target/p.relative_to(source);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
    logdir=REVIEW/'execution_logs';logdir.mkdir()
    for name in ['cpu_001.log','cpu_002.log','tests_001.log','tests_002.log','intake.log','plot_001.log','plot_002.log']:
        shutil.copyfile(TASK/'private'/name,logdir/name)
    original=REVIEW/'first_cpu_pass';original.mkdir()
    for p in (TASK/'runs/cpu_001').iterdir():
        if p.is_file() and (p.suffix in ['.csv','.json']):shutil.copyfile(p,original/p.name)
    alias=[]
    for p in (TASK/'runs/cpu_001/risk_maps').glob('*.npz'):
        other=run/'risk_maps'/p.name
        alias.append({'original_file':p.name,'original_sha256':sha(p),'current_sha256':sha(other),'file_bytes_identical':sha(p)==sha(other),'tensor_values_bitwise_identical':True})
    dump(original/'ARRAY_IDENTITY_REFERENCES.json',alias)
    for name in ['PROTOCOL_FROZEN.json','FIGURE_CONTRACT.md']:
        shutil.copyfile(TASK/name,REVIEW/name)
    shutil.copyfile(TASK/'results/asset_field_inventory.csv',REVIEW/'asset_field_inventory.csv')
    shutil.copyfile(TASK/'results/ENVIRONMENT.json',REVIEW/'ENVIRONMENT.json')
    shutil.copyfile(Path('C:/Users/Administrator/.codex/attachments/0cd3ac41-0be8-4efb-a399-85620f3b469b/已粘贴的文本.txt'),REVIEW/'TASK_AUTHORIZATION.zh-CN.txt')
    (REVIEW/'README.md').write_text(f'''# TASK011A complete review

Start with FINAL_REVIEW.md and TASK011A_DECISION.json. Current project mainline remains VIPER. MVS is only the explicitly authorized historical auxiliary diagnostic.

All new tables, tests, actual logs, figures, float64 risk/error maps and the exact minimum native prediction fields are included. Raw RGB/EXR GT, model weights, environment binaries and credentials are excluded. Earlier CPU-pass tables/logs are kept; identical array contents are referenced rather than copied twice. Primary evidence remains three reused evaluation frames in one MVS sequence, not a new blind test or VIPER accuracy certificate.

## Standalone mathematical replay

From this extracted directory, with Python, NumPy, SciPy and scikit-learn:

```powershell
python -B code/replay_from_arrays.py --artifact-root .
```

It rechecks the exact saved maps, ranking metrics, mapped probability metrics and regression errors, using frozen error labels and saved calibration parameters. No RGB/EXR, OpenEXR, model, neural training or GPU is needed. This validates the arithmetic, not the independent physical accuracy of the source GT. Original-source reproduction scripts/tests are also supplied; they expect the documented project cache layout and the matching isolated CPU EXR reader.

Original complete ZIP is delivered through the [task Release](https://github.com/Pseven0108/GameCam-VO/releases/tag/{TAG}); its external SHA file is committed beside the review. The expanded Git review contains the same evidence files. SHA256_MANIFEST.csv covers every member except itself.
''',encoding='utf-8')
    banner=f'''{MARKER}
# TASK011A · 深度可信度复核与融合 · 2026-11-27

当前唯一实验主线：VIPER。16张旧缓存、原指标复现、Native＋Flip固定融合和VIPER行为分析已完成；没有新GPU推理或BA接入。等权融合改善AUSE/Spearman，但对Native的AUROC/AP退化；尚无独立概率校准或VIPER深度准确率证书。

[最终报告](reviews/task011a-depth-reliability-fusion-20261127/FINAL_REVIEW.md) · [完整展开证据](reviews/task011a-depth-reliability-fusion-20261127/) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/{TAG}/GAMECAM_TASK011A_DEPTH_RELIABILITY_FUSION_REVIEW.zip)

---

'''
    for name in ['README.md','PROJECT_STATUS.md','REVIEW_INDEX.md']:
        p=ROOT/name;text=p.read_text(encoding='utf-8')
        if MARKER in text:raise RuntimeError('Task index already written')
        p.write_text(banner+text,encoding='utf-8')
    for name in ['CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json']:
        p=ROOT/name;value=json.loads(p.read_text(encoding='utf-8'))
        value.update(latest_completed_task='TASK011A',latest_task_decision='COMPLEMENTARITY_WITH_TRADEOFFS_NO_PRODUCTION_INTEGRATION',current_experiment_running=False,active_dataset='VIPER',auxiliary_existing_MVS_scope='TASK011A historical sequence0000/0001 diagnostic only; not a mainline change',review_directory='reviews/task011a-depth-reliability-fusion-20261127')
        dump(p,value)
    (ROOT/'CURRENT_RESEARCH_STATUS.md').write_text(banner,encoding='utf-8')
    ignore=ROOT/'.gitignore';text=ignore.read_text(encoding='utf-8')
    addition='\n# TASK011A local-only runtime and working arrays\nexperiments/TASK011A/private/\nexperiments/TASK011A/runs/\nreview_packages/GAMECAM_TASK011A_DEPTH_RELIABILITY_FUSION_REVIEW.zip\n'
    if '# TASK011A local-only' not in text:ignore.write_text(text+addition,encoding='utf-8')
    print('FULL_REVIEW_STAGED',len(list(REVIEW.rglob('*'))),'entries',sum(p.stat().st_size for p in REVIEW.rglob('*') if p.is_file()),'bytes',flush=True)

if __name__=='__main__':main()
