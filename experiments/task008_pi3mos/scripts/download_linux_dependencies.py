"""Download binary Linux dependencies without installing them locally."""
from email.parser import Parser
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from pip._vendor.packaging.requirements import Requirement

WHEEL=Path(r'D:\aaa\external_models\task008-linux-wheels\torch-2.3.1+cu121-cp310-cp310-linux_x86_64.whl')
with zipfile.ZipFile(WHEEL) as z:
    meta=Parser().parsestr(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))).decode())
env={'python_version':'3.10','python_full_version':'3.10.22','platform_system':'Linux','sys_platform':'linux',
     'platform_machine':'x86_64','os_name':'posix','extra':'','implementation_name':'cpython',
     'platform_python_implementation':'CPython','implementation_version':'3.10.22','platform_release':'','platform_version':''}
requirements=[]
for value in meta.get_all('Requires-Dist'):
    r=Requirement(value)
    if r.marker is None or r.marker.evaluate(env):requirements.append(r.name+str(r.specifier))
requirements+=[
    'numpy==1.26.4','pillow','einops','huggingface_hub==0.26.5','safetensors','plyfile','gdown==5.2.0',
    'opencv-python-headless==4.10.0.84','nvidia-nvjitlink-cu12','mpmath','MarkupSafe','packaging',
    'pyyaml','requests','urllib3','certifi','charset_normalizer','idna','tqdm','beautifulsoup4','soupsieve','PySocks']
requirements=list(dict.fromkeys(requirements))
out=Path(r'D:\aaa\external_models\task008-linux-dependency-wheels');out.mkdir(exist_ok=False)
args=[sys.executable,'-m','pip','download','--no-cache-dir','--no-deps','--only-binary=:all:',
      '--python-version','310','--implementation','cp','--abi','cp310','--dest',str(out)]
for platform in ['linux_x86_64','manylinux1_x86_64','manylinux2014_x86_64','manylinux_2_17_x86_64','manylinux_2_27_x86_64','manylinux_2_28_x86_64']:
    args+=['--platform',platform]
args+=requirements
(out/'REQUESTED_REQUIREMENTS.json').write_text(json.dumps({'Torch_wheel_requires_dist_Linux':requirements,'local_environment_install':False},indent=2)+'\n')
subprocess.run(args,check=True)
