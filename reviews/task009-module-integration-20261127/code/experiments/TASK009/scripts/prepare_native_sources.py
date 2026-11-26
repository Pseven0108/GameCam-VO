import io
import json
import subprocess
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
original = Path(r'D:\aaa\GameCam-VO\baselines\droid_w\upstream\thirdparty\lietorch')
destination = root / 'external/DROID-W/thirdparty/lietorch'
commits = [(original, '0fa9ce8ffca86d985eca9e189a99690d6f3d4df6', destination),
           (original / 'eigen', '824272cde8ca2541e8b67b0887f5ded92b128d1f', destination / 'eigen')]
for repo, commit, target in commits:
    target.mkdir(parents=True, exist_ok=True)
    content = subprocess.check_output(['git', '-C', str(repo), 'archive', commit])
    with tarfile.open(fileobj=io.BytesIO(content)) as t:
        for member in t.getmembers():
            if not (target / member.name).resolve().is_relative_to(target.resolve()) or member.issym() or member.islnk():
                raise ValueError('Unsafe archive member')
        t.extractall(target, filter='data')

# Modern ATen dispatcher metadata spelling, without changing numerical bodies.
for relative in ['lietorch/src/lietorch_cpu.cpp', 'lietorch/src/lietorch_gpu.cu',
                 'lietorch/extras/corr_index_kernel.cu']:
    p = destination / relative
    text = p.read_text()
    import re
    text = re.sub(r'(\w+)\.type\(\)', r'\1.scalar_type()', text)
    p.write_text(text)

for p in [destination / 'setup.py', root / 'external/DROID-W/setup.py']:
    lines = p.read_text().splitlines()
    lines = [line for line in lines if '-gencode=arch=compute_' not in line]
    p.write_text('\n'.join(lines) + '\n')

(root / 'experiments/TASK009/intake/native_source_preparation.json').write_text(json.dumps({
    'source_commits': [dict(path=str(r), commit=c) for r, c, _ in commits],
    'scope': 'isolated candidate only; numerical kernel formulas unchanged',
    'changes': ['ATen scalar_type dispatcher metadata', 'sm_120 build via TORCH_CUDA_ARCH_LIST']
}, indent=2))
