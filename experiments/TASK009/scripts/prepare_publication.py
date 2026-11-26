"""Build an explicit GitHub publication allowlist without credentials or Git edits."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = Path('D:/aaa/GameCam-VO')
PUBLISH = ROOT / 'experiments/TASK009/private/publication'
REVIEW_NAME = 'task009-module-integration-20261127'
REVIEW = ROOT / 'reviews' / REVIEW_NAME
TEXT = {'.md', '.py', '.sh', '.ps1', '.json', '.jsonl', '.csv', '.yaml', '.txt', '.log', '.patch', '.sha256'}


def main():
    previous = json.loads((PUBLISH / 'parent_files.json').read_text(encoding='utf-8'))
    receipt = json.loads((ROOT / 'deliveries/TASK009_PACKAGE_VERIFICATION.json').read_text(encoding='utf-8'))
    prefix = f'''# GameCam-VO · TASK009 本地模块迁移原型

2026-11-27。已完成本地 RTX5060 的9次真实 DROID-W 运行与独立模块验证；本轮已停止推理。

[最终评审](reviews/{REVIEW_NAME}/FINAL_REVIEW.md) · [完整展开评审包](reviews/{REVIEW_NAME}) · [下载完整ZIP](review_packages/GAMECAM_TASK009_REVIEW.zip) · [ZIP SHA-256](review_packages/GAMECAM_TASK009_REVIEW.zip.sha256)

- **本窗口优先保留 BA-Track 静态目标辅助**：Sim3 ATE 2.733–3.500，对比本地E0 6.497–6.619。
- π³MOS门控与组合未改善；WildGS尚未通过跨域准入。Easi attention与LEAP仅独立推理，不声称轨迹收益。
- 32帧 Night val007 RGB301..332，216×384，stride1；距离是游戏单位，不是米。不是原R2复现，没有第三人称/跨场景泛化证据。
- 23项CPU测试、3次同输入CUDA向量化逐位核验、9组轨迹指标复算通过。
- 项目Conda实际目录 `D:\\aaa\\envs\\gamecam-vo`，缓存和临时存储在D；107416文件迁移SHA一致，旧路径Junction兼容。系统/WSL发行版根盘未整体迁移。
- 原基线、权重、历史结果和6份用户dirty文件受保护；本轮无远程操作、无训练、无重启/关机。
- ZIP：{receipt['zip_bytes']:,} bytes；CRC PASS；{receipt['internal_sha256_verified']}项内部SHA通过；SHA-256 `{receipt['zip_sha256']}`。

本轮独立于已封存TASK008支线；按新任务授权只读复用已有概率缓存，没有恢复其服务器实验。
可重跑代码在 `gamecam/modules/` 与 `experiments/TASK009/scripts/`；统一说明配置在 `configs/task009/local_exploration.json`。
完整作用范围、耗时边界、失败尝试与未完成项目见评审报告。权重、环境二进制、原始RGB/GT和大型先验不公开上传。

'''
    files = {}

    def add(path, destination=None):
        path = Path(path)
        key = destination or path.relative_to(ROOT).as_posix()
        if key in files:
            raise ValueError(f'Duplicate publication path: {key}')
        files[key] = path

    for label, target in [('readme', 'README.md'), ('status', 'PROJECT_STATUS.md'), ('index', 'REVIEW_INDEX.md')]:
        content = prefix + f'<details>\n<summary>上一阶段封存记录（{previous["parent_sha"][:12]}，历史状态）</summary>\n\n' + previous[label] + '\n\n</details>\n'
        path = PUBLISH / target
        path.write_text(content, encoding='utf-8')
        add(path, target)
    ignore = PUBLISH / '.gitignore'
    ignore.write_text(previous['gitignore'].rstrip() + '\n\n# TASK009 isolated local research assets\n/runtime/\n/external/\n/experiments/TASK009/outputs/\n/experiments/TASK009/private/\n/maintenance/STORAGE_MIGRATION_20261127/*.files.jsonl\n', encoding='utf-8')
    add(ignore, '.gitignore')
    for directory in [REVIEW, ROOT / 'gamecam', ROOT / 'experiments/TASK009/scripts', ROOT / 'experiments/TASK009/tests', ROOT / 'configs/task009']:
        for path in sorted(directory.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                add(path)
    for path in sorted((ROOT / 'docs').glob('TASK009*.md')):
        add(path)
    add(ROOT / 'experiments/TASK009/FINAL_REVIEW.md')
    add(ROOT / 'scripts/run_gamecam_local.py')
    add(ORIGINAL / 'AGENTS.md', 'AGENTS.md')
    add(ORIGINAL / 'docs/LOCAL_EXPERIMENT_WORKFLOW.md', 'docs/LOCAL_EXPERIMENT_WORKFLOW.md')
    for name in ['GAMECAM_TASK009_REVIEW.zip', 'GAMECAM_TASK009_REVIEW.zip.sha256', 'TASK009_PACKAGE_VERIFICATION.json']:
        add(ROOT / 'deliveries' / name, 'review_packages/' + name)
    entries = []
    patterns = [re.compile(x, re.I) for x in (r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
                r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
                r'https?://[^\s\"<>]+[?&](?:X-Amz-Signature|X-Goog-Signature|token|access_token|auth)=')]
    for key, path in sorted(files.items()):
        data = path.read_bytes()
        text = path.suffix in TEXT or path.name == '.gitignore'
        if text:
            decoded = data.decode('utf-8')
            if any(p.search(decoded) for p in patterns):
                raise ValueError(f'Publication scan rejected {key}')
        entries.append({'path': key, 'source': str(path), 'encoding': 'utf-8' if text else 'base64',
                        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                        'git_blob_sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()})
    result = {'branch': 'codex/task009-module-integration-20261127', 'parent_sha': previous['parent_sha'],
              'entries': entries, 'file_count': len(entries), 'total_bytes': sum(r['bytes'] for r in entries),
              'scan': 'PASS', 'public_visibility_required': True}
    (PUBLISH / 'allowlist.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}, indent=2))
    print('binary files:', sum(r['encoding'] == 'base64' for r in entries))


if __name__ == '__main__':
    main()
