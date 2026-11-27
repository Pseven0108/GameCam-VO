"""Maintain an owned current-status block, preserving unrelated/history text."""
import argparse,json,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from common import ROOT,TASK,dump

START='<!-- TASK011B_CURRENT_START -->'
END='<!-- TASK011B_CURRENT_END -->'


def prepend(path,block):
    previous=path.read_text(encoding='utf-8-sig') if path.exists() else ''
    previous=re.sub(re.escape(START)+r'.*?'+re.escape(END)+r'\s*','',previous,flags=re.S)
    path.write_text(START+'\n'+block.strip()+'\n'+END+'\n\n'+previous,encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--published-commit');a=p.parse_args()
    progress=json.loads((TASK/'gpu_results/PROGRESS.json').read_text())
    date=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M +08:00')
    done=a.published_commit is not None
    if done:
        receipt=json.loads((TASK/'private/publication/PUBLICATION_RECEIPT.json').read_text())
        if receipt['status']!='PUBLIC_VERIFIED' or receipt['commit']!=a.published_commit:
            raise RuntimeError('Do not mark public delivery before actual verification')
        title='TASK011B 已完成并公开交付，等待评审'
        link='https://github.com/Pseven0108/GameCam-VO/blob/'+a.published_commit+'/reviews/task011b-validity-aware-cadp-dr-20261127/FINAL_REVIEW.md'
        body=f'全部140个计划终态已归档并核验。固定提交评审：[FINAL_REVIEW.md]({link})。完整ZIP：[公开评审包]({receipt["zip_public_url"]})。'
    else:
        title='TASK011B 正在执行 GPU 下游验证'
        body=f'本地进度快照：{progress["terminal"]}/140 个正式终态已收集。请读取D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/gpu_results/PROGRESS.json及同目录批次完成标记判断实时状态，不重复启动监督器。'
    block=f'''# {title}

更新时间：{date}。唯一主数据集：VIPER。当前授权：20个固定64帧窗口 × 7组，640×360、stride1、seed43、buffer500；远端3090串行运行，原生生产Baseline保持不变。

{body}

正式数值协议为NATIVE_MOTION_FILTER_AUTOCAST_V2，早期10个FP32工程试跑不纳入正式估计。R0/R1辅助缓存诊断与R3轨迹结果分开。用户本次暂不要求实时浏览器可视化；不关机、不重启、不进入下一阶段。

本段下方均为此前记录，不能将其GPU不可用、0次运行或TASK011A为当前阶段的描述理解为本段更新时间的状态。'''
    canonical=Path('D:/aaa/GameCam-VO')
    for name in ('CURRENT_RESEARCH_STATUS.md','PROJECT_STATUS.md'):
        prepend(canonical/name,block)
    # The isolated task worktree has no unrelated work to merge into its own
    # concise live pointer. Completed published files remain immutable.
    if not done:
        for name in ('CURRENT_RESEARCH_STATUS.md','PROJECT_STATUS.md'):
            (ROOT/name).write_text(block+'\n',encoding='utf-8')
        (TASK/'EXECUTION_STATE.md').write_text(block+'\n',encoding='utf-8')
    dump(TASK/'private/STATUS_POINTER_SYNC.json',dict(
        updated=date,formal_terminal_snapshot=progress['terminal'],public_delivery_verified=done,
        preserved_unrelated_canonical_text=True,next_stage_started=False))
    print('CANONICAL_STATUS_POINTER_SYNCHRONIZED',progress['terminal'],done,flush=True)


if __name__=='__main__':main()
