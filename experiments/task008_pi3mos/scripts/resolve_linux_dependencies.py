"""Resolve compatible Linux-only wheels, reusing exact downloaded CUDA assets."""
import json
from pathlib import Path
import subprocess
import sys

out = Path(r'D:\aaa\external_models\task008-linux-dependency-wheels')
requirements = json.loads((out/'REQUESTED_REQUIREMENTS.json').read_text())['Torch_wheel_requires_dist_Linux']
args = [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--python-version', '310',
        '--implementation', 'cp', '--abi', 'cp310', '--dest', str(out), '--find-links', str(out)]
for platform in ['linux_x86_64','manylinux1_x86_64','manylinux2014_x86_64','manylinux_2_17_x86_64','manylinux_2_27_x86_64','manylinux_2_28_x86_64']:
    args += ['--platform', platform]
with (out/'RESOLUTION.log').open('xb') as f:
    r = subprocess.run(args + requirements, stdout=f, stderr=subprocess.STDOUT)
print(json.dumps({'exit_code': r.returncode, 'log': str(out/'RESOLUTION.log'), 'local_install': False}))
raise SystemExit(r.returncode)
