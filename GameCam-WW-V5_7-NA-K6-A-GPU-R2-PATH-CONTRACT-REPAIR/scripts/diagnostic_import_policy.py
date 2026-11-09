"""Read-only Python import policy; session file permissions are never widened."""
import hashlib, importlib.abc, importlib.machinery, os, pathlib, sys, tempfile

IMPORT_POLICY = {
    'version': 'gamecam-python-import-policy-v1',
    'environment_cache': 'DEFAULT_PATH_READ_ONLY',
    'sealed_project_modules': 'VERIFIED_SOURCE_ONLY',
    'session_pycache_prefix': False,
    'bytecode_writes': False,
    'matplotlib_config': 'MODEL_OUTPUT_ONLY_AGG',
    'generic_temp': 'MODEL_OUTPUT_ONLY_IPC_FALLBACK_UNCHANGED',
}

def sanitized_worker_environment(parent, pinned):
    if 'PYTHONPYCACHEPREFIX' in pinned:
        raise RuntimeError('SESSION_PYCACHE_PREFIX_FORBIDDEN')
    env = dict(parent)
    env.pop('PYTHONPYCACHEPREFIX', None)
    env.update(pinned)
    if env.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise RuntimeError('BYTECODE_WRITES_MUST_BE_DISABLED')
    return env

def prepare_import_scratch(candidate):
    output = pathlib.Path(candidate['planned_model_output'])
    scratch = output / 'import_tmp'
    scratch.mkdir(mode=0o700, exist_ok=False)
    os.environ['TMPDIR'] = str(scratch)
    tempfile.tempdir = str(scratch)
    return scratch

def validate_worker_import_policy(candidate):
    if candidate.get('python_import_policy') != IMPORT_POLICY:
        raise RuntimeError('PYTHON_IMPORT_POLICY_MISMATCH')
    if 'PYTHONPYCACHEPREFIX' in candidate['pinned_environment']:
        raise RuntimeError('SESSION_PYCACHE_PREFIX_FORBIDDEN')
    if os.environ.get('PYTHONPYCACHEPREFIX') is not None or sys.pycache_prefix is not None:
        raise RuntimeError('PYTHON_CACHE_PREFIX_INHERITED')
    expected_mpl = str(pathlib.Path(candidate['planned_model_output']) / 'matplotlib')
    if os.environ.get('MPLCONFIGDIR') != expected_mpl or os.environ.get('MPLBACKEND') != 'Agg':
        raise RuntimeError('MATPLOTLIB_IMPORT_CACHE_NOT_PINNED')
    if not sys.dont_write_bytecode or os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise RuntimeError('BYTECODE_WRITES_MUST_BE_DISABLED')

# Both normal imports and Torch Hub direct specs use the same pinned byte loader.
from verified_dynamic_source import VerifiedSourceFinder, VerifiedDynamicSourceLoader
