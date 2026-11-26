"""Load upstream pure-PyTorch sum/mean without optional binary imports.

The installed PyG wheel requires newer glibc than this WSL distribution.
DROID-W uses scatter_sum and scatter_mean, whose *official implementations*
already call PyTorch scatter_add_. No custom binary is needed for these APIs.
All source function bodies are loaded unchanged from the installed package.
"""
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
import types


def install():
    if 'torch_scatter' in sys.modules:
        raise RuntimeError('Select the scatter compatibility path before model imports')
    spec=importlib.util.find_spec('torch_scatter')
    if spec is None or not spec.submodule_search_locations:
        raise ImportError('Install the official torch-scatter package first')
    directory=Path(next(iter(spec.submodule_search_locations)))
    package=types.ModuleType('torch_scatter')
    package.__path__=[str(directory)]
    package.__file__=str(directory/'__init__.py')
    package.__package__='torch_scatter'
    sys.modules['torch_scatter']=package
    module=importlib.import_module('torch_scatter.scatter')
    for name in ('scatter_sum','scatter_add','scatter_mean'):
        setattr(package,name,getattr(module,name))
    return {'mode':'UPSTREAM_PURE_PYTORCH_SUM_MEAN_ONLY',
            'scatter_py_sha256':hashlib.sha256((directory/'scatter.py').read_bytes()).hexdigest(),
            'utils_py_sha256':hashlib.sha256((directory/'utils.py').read_bytes()).hexdigest(),
            'custom_scatter_binary_loaded':False,'native_torch_scatter_add_used':True}
