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

class _VerifiedSourceLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, filename, expected_sha256, events):
        super().__init__(fullname, filename)
        self.expected_sha256 = expected_sha256
        self.events = events
    def get_code(self, fullname):
        # Protected source is already pinned. Do not probe an unpinned project pyc.
        data = self.get_data(self.path)
        actual = hashlib.sha256(data).hexdigest()
        if actual != self.expected_sha256:
            raise RuntimeError('IMPORT_SOURCE_SHA_DRIFT:' + self.path)
        self.events.append({'module': fullname, 'path': self.path,
                            'sha256': actual, 'strategy': 'VERIFIED_SOURCE_ONLY'})
        return self.source_to_code(data, self.path)

class VerifiedSourceFinder(importlib.abc.MetaPathFinder):
    def __init__(self, source_root, source_records, external_records=()):
        root = pathlib.Path(source_root)
        self.identities = {str((root / r['path']).resolve()): r['sha256']
                           for r in source_records if r['path'].endswith('.py')}
        self.identities.update({str(pathlib.Path(r['path']).resolve()): r['sha256']
                                for r in external_records if r['path'].endswith('.py')})
        self.events = []
    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or not isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            return None
        lexical = pathlib.Path(spec.origin).absolute()
        resolved = lexical.resolve()
        expected = self.identities.get(str(resolved))
        if expected is None:
            return None
        if lexical != resolved or lexical.is_symlink():
            raise RuntimeError('IMPORT_SOURCE_SYMLINK_FORBIDDEN:' + str(lexical))
        spec.loader = _VerifiedSourceLoader(fullname, str(lexical), expected, self.events)
        return spec
    def install(self):
        if any(isinstance(x, VerifiedSourceFinder) for x in sys.meta_path):
            raise RuntimeError('VERIFIED_SOURCE_FINDER_ALREADY_INSTALLED')
        sys.meta_path.insert(0, self)
        return self
