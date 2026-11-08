"""External file and loader-boundary pins. Stdlib-only until the guarded importer is used."""
import argparse
import csv
import functools
import hashlib
import importlib.abc
import importlib.machinery
import inspect
import io
import json
import os
from pathlib import Path
import socket
import sys
import time
import traceback

FROZEN_SPEC_SHA256 = '11e2172ad1c9fe4ff7116381a264c7f4fcf9535db9352d320140748d9a92be33'
SPEC_VERSION = 'K6-A-R2-PIN-v1'
CHECKS = {'config','weights','paths','manifest','camera','input','offline','loader_hooks','revision'}

class PinError(RuntimeError):
    def __init__(self, reason, code='BLOCKED_BY_WEIGHT_PIN'):
        self.code = code
        self.reasons = [str(reason)]
        super().__init__(str(reason))

def require(ok, reason, code='BLOCKED_BY_WEIGHT_PIN'):
    if not ok:
        raise PinError(reason, code)

def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()

def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for data in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()

def identity(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))

def native(record, real=False):
    return Path(record[('real_' if real else 'path_') + ('windows' if os.name == 'nt' else 'linux')])

class RuntimePins:
    def __init__(self, root, event_sink=None):
        self.root = Path(root).resolve()
        self.event_sink = event_sink
        self.events = []
        self.gate = None
        self._spec_data = (self.root / 'config/dependency_pins.json').read_bytes()
        require(sha_bytes(self._spec_data) == FROZEN_SPEC_SHA256, 'PIN_SPEC_SHA_MISMATCH', 'BLOCKED_BY_RUNTIME_MANIFEST')
        self.spec = json.loads(self._spec_data)
        require(self.spec.get('version') == SPEC_VERSION, 'PIN_SPEC_VERSION', 'BLOCKED_BY_RUNTIME_MANIFEST')
        require(set(self.spec.get('checks', {})) == CHECKS and all(self.spec['checks'][k] is True for k in CHECKS), 'REQUIRED_CHECKER_DISABLED', 'BLOCKED_BY_LOADER_COVERAGE')
        self._frozen_files = {}
        for name, record in self.spec['files'].items():
            rel = Path(record['path'])
            require(not rel.is_absolute() and '..' not in rel.parts, 'LOCAL_PIN_PATH_ESCAPE', 'BLOCKED_BY_RUNTIME_MANIFEST')
            p = self.root / rel
            data = p.read_bytes()
            require(len(data) == record['bytes'] and sha_bytes(data) == record['sha256'], 'EXTERNAL_MANIFEST_SHA_MISMATCH:' + name, 'BLOCKED_BY_RUNTIME_MANIFEST')
            self._frozen_files[name] = data
        rows = list(csv.DictReader(io.StringIO(self._frozen_files['frozen_weight_manifest.csv'].decode('utf-8-sig'))))
        require(len(rows) == len(self.spec['weights']) == 4, 'WEIGHT_ALLOWLIST_MUST_HAVE_FOUR', 'BLOCKED_BY_WEIGHT_PIN')
        self.weights = {r['id']: r for r in self.spec['weights']}
        require(len(self.weights) == 4, 'DUPLICATE_WEIGHT_ID')
        for row in rows:
            r = self.weights.get(row['dependency_id'])
            require(r is not None and r['sha256'] == row['expected_sha256'] == row['sha256'] and r['bytes'] == int(row['bytes']) and r['path_linux'] == row['path_linux'] and r['path_windows'] == row['path_windows'], 'INHERITED_WEIGHT_ALLOWLIST_CHANGED')
        self._checked_original = None

    def event(self, kind, **fields):
        item = dict(event=kind, unix_time=time.time(), **fields)
        self.events.append(item)
        if self.event_sink is not None:
            self.event_sink(item)
        return item

    def assert_manifest(self):
        require(sha_bytes((self.root / 'config/dependency_pins.json').read_bytes()) == FROZEN_SPEC_SHA256, 'PIN_SPEC_CHANGED_DURING_PROCESS', 'BLOCKED_BY_RUNTIME_MANIFEST')
        for name, r in self.spec['files'].items():
            data = (self.root / r['path']).read_bytes()
            require(len(data) == r['bytes'] and sha_bytes(data) == r['sha256'], 'EXTERNAL_MANIFEST_CHANGED:' + name, 'BLOCKED_BY_RUNTIME_MANIFEST')

    def checked_file(self, record, request=None, read=False, code='BLOCKED_BY_WEIGHT_PIN'):
        expected = native(record)
        requested = expected if request is None else request
        require(isinstance(requested, (str, bytes, os.PathLike)), 'UNSUPPORTED_FILE_OBJECT', code)
        if isinstance(requested, bytes):
            requested = os.fsdecode(requested)
        p = Path(requested)
        require(p.is_absolute(), 'RELATIVE_LOAD_PATH_NOT_ALLOWED:' + str(p), code)
        require(identity(p) == identity(expected), 'LOAD_PATH_NOT_ALLOWLISTED:' + str(p), code)
        try:
            real_before = p.resolve(strict=True)
            require(identity(real_before) == identity(native(record, real=True)), 'SYMLINK_TARGET_CHANGED:' + str(p), code)
            st = p.stat()
            require(st.st_size == record['bytes'], 'FILE_SIZE_MISMATCH:' + str(p), code)
            data = p.read_bytes() if read else None
            actual = sha_bytes(data) if read else digest_file(p)
            require(actual == record['sha256'], 'FILE_SHA_MISMATCH:' + str(p), code)
            st_after = p.stat()
            require(identity(p.resolve(strict=True)) == identity(real_before) and (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) == (st_after.st_dev, st_after.st_ino, st_after.st_size, st_after.st_mtime_ns), 'FILE_CHANGED_DURING_CHECK:' + str(p), code)
        except OSError as exc:
            raise PinError('PIN_FILE_UNAVAILABLE:' + str(p), code) from exc
        return data if read else dict(path=str(p), real_path=str(real_before), bytes=st.st_size, sha256=actual)

    def check_revision(self):
        hf = self.spec['hf']
        p = Path(hf['ref_path_windows' if os.name == 'nt' else 'ref_path_linux'])
        try:
            raw = p.read_bytes()
        except OSError as exc:
            raise PinError('HF_REF_MISSING') from exc
        require(len(raw) == hf['ref_bytes'] and sha_bytes(raw) == hf['ref_sha256'] and raw.decode().strip() == hf['revision'], 'HF_SNAPSHOT_REVISION_CHANGED')
        weight = self.weights[hf['weight_id']]
        require(hf['revision'] in native(weight).parts, 'HF_SNAPSHOT_PATH_REVISION_CHANGED')

    def read_original_config(self):
        self.assert_manifest()
        raw = self.checked_file(self.spec['config'], read=True, code='BLOCKED_BY_CONFIG_PIN')
        # Parsing consumes the exact bytes just hashed, never a second unchecked read.
        cfg = json.loads(raw.decode('utf-8-sig'))
        self.verify_camera(cfg)
        require(cfg['max_frames'] == 60 and cfg['stride'] == 1 and cfg['tracking']['buffer'] == 350 and cfg['tracking']['warmup'] == 12 and cfg['mapping']['enable'] is False, 'NATIVE_CONFIGURATION_CONTRACT', 'BLOCKED_BY_CONFIG_PIN')
        self._checked_original = cfg
        self.event('config_checked_before_parse', sha256=sha_bytes(raw), bytes=len(raw), source=str(native(self.spec['config'])))
        return cfg

    def verify_camera(self, cfg):
        cases = json.loads(self._frozen_files['cases.json'].decode('utf-8-sig'))
        require(len(cases) == 1 and cases[0]['case_id'] == 'V56_01_middle', 'CASE_CONTRACT', 'BLOCKED_BY_CONFIG_PIN')
        case = cases[0]
        k4raw = self.checked_file(self.spec['k4_live_contract'], read=True, code='BLOCKED_BY_CONFIG_PIN')
        require(k4raw == self._frozen_files['k4_input_contract.json'], 'K4_LIVE_CONTRACT_CHANGED', 'BLOCKED_BY_CONFIG_PIN')
        k4 = json.loads(k4raw.decode('utf-8-sig'))
        c = cfg['cam']
        sx = (c['W_out'] + 2*c['W_edge']) / c['W']
        sy = (c['H_out'] + 2*c['H_edge']) / c['H']
        actual = [c['fx']*sx, c['fy']*sy, c['cx']*sx-c['W_edge'], c['cy']*sy-c['H_edge']]
        K = k4['K_input']
        require(actual == [K[0][0],K[1][1],K[0][2],K[1][2]] == case['K4'] and K == case['K_input'], 'CAMERA_INTRINSICS_CHANGED', 'BLOCKED_BY_CONFIG_PIN')
        require(c['W'] == c['W_out'] == case['width'] == 512 and c['H'] == c['H_out'] == case['height'] == 288 and c['W_edge'] == c['H_edge'] == 0 and 'distortion' not in c, 'CAMERA_RESIZE_CROP_CONTRACT', 'BLOCKED_BY_CONFIG_PIN')
        require(cfg['data']['input_folder'] == case['rgb_folder_linux'].rsplit('/rgb', 1)[0], 'RGB_ROOT_CHANGED', 'BLOCKED_BY_CONFIG_PIN')
        rows = list(csv.DictReader(io.StringIO(self._frozen_files['k4_input_frames.csv'].decode('utf-8-sig'))))
        require(len(rows) == len(case['frames']) == 120, 'INPUT_MANIFEST_COUNT', 'BLOCKED_BY_CONFIG_PIN')
        for i, (r, f) in enumerate(zip(rows, case['frames'])):
            require(int(r['ordinal']) == i and int(r['published_frame_index']) == f['frame'] == 7953+i and r['png_sha256'] == f['png_sha256'] and r['decoded_bgr_sha256'] == f['decoded_bgr_sha256'] and r['all_pass'] == 'True', 'K4_FROZEN_FRAME_MAPPING:' + str(i), 'BLOCKED_BY_CONFIG_PIN')

    def effective_config(self, output):
        original = self.read_original_config()
        cfg = json.loads(json.dumps(original))
        cfg['max_frames'] = 120
        cfg['data']['output'] = str(output)
        comparison = json.loads(json.dumps(cfg))
        comparison['max_frames'] = original['max_frames']
        comparison['data']['output'] = original['data']['output']
        require(comparison == original, 'UNAPPROVED_CONFIG_MUTATION', 'BLOCKED_BY_CONFIG_PIN')
        return cfg

    def static_check(self):
        self.read_original_config()
        self.check_revision()
        records = [self.checked_file(r) for r in self.weights.values()]
        self.event('static_dependency_check_passed', weights=len(records), model_imported=False)
        return dict(passed=True, weights=records, config_sha256=self.spec['config']['sha256'], pin_spec_sha256=FROZEN_SPEC_SHA256, camera_verified=True, input_manifest_verified=True, torch_imported='torch' in sys.modules, checkpoint_deserialized=False)

    def check_environment(self):
        for name, value in self.spec['environment'].items():
            require(os.environ.get(name) == value, 'PINNED_ENVIRONMENT_CHANGED:' + name, 'BLOCKED_BY_LOADER_COVERAGE')
        require(os.environ.get('TIMM_USE_OLD_CACHE', '0') == '0', 'OLD_CACHE_FALLBACK_FORBIDDEN', 'BLOCKED_BY_LOADER_COVERAGE')

    def install_before_import(self):
        self.check_environment()
        require(self.gate is None, 'HOOK_GATE_ALREADY_INSTALLED', 'BLOCKED_BY_LOADER_COVERAGE')
        disallowed = [n for n in sys.modules if n == 'torch' or n.startswith(('torch.', 'safetensors.torch', 'timm', 'src.', 'mono.', 'huggingface_hub'))]
        require(not disallowed, 'LOADERS_BOUND_BEFORE_PIN_INSTALL:' + ','.join(disallowed[:8]), 'BLOCKED_BY_LOADER_COVERAGE')
        self.gate = LoaderGate(self)
        self.gate.install()
        self.event('loader_gate_installed_before_dependency_import')
        return self.gate

    def assert_hooks(self, require_torch=False):
        require(self.gate is not None, 'LOADER_GATE_MISSING', 'BLOCKED_BY_LOADER_COVERAGE')
        self.gate.assert_integrity()
        if require_torch:
            require('torch' in sys.modules and ('torch', 'load') in self.gate.bindings and ('torch.serialization','load') in self.gate.bindings, 'TORCH_LOADER_NOT_COVERED', 'BLOCKED_BY_LOADER_COVERAGE')

    def boundary(self, loader, original, *args, **kwargs):
        self.assert_manifest()
        self.assert_hooks()
        self.check_environment()
        request = args[0] if args else kwargs.get('f' if loader == 'torch.load' else 'filename')
        start = time.time()
        event = dict(loader=loader, requested_path=os.fsdecode(request) if isinstance(request,(str,bytes,os.PathLike)) else str(type(request)), started_unix=start, positional_argument_count=len(args), keyword_names=sorted(kwargs))
        try:
            record = next((r for r in self.weights.values() if request is not None and isinstance(request,(str,bytes,os.PathLike)) and identity(request) == identity(native(r))), None)
            require(record is not None, 'UNREGISTERED_WEIGHT:' + event['requested_path'])
            require(record['loader'] == loader, 'UNEXPECTED_LOADER:' + loader)
            self.check_revision()
            checked = self.checked_file(record, request)
            self.event('weight_load_started', dependency_id=record['id'], **event, **checked)
            value = original(*args, **kwargs)
            self.event('weight_load_completed', dependency_id=record['id'], loader=loader, started_unix=start, finished_unix=time.time(), sha256=record['sha256'])
            return value
        except BaseException as exc:
            self.event('weight_load_rejected_or_failed', **event, finished_unix=time.time(), status=getattr(exc,'code','BLOCKED_BY_DEPENDENCY_INITIALIZATION'), error=str(exc), traceback=traceback.format_exc())
            raise

class _AfterExec(importlib.abc.Loader):
    def __init__(self, original, gate):
        self.original, self.gate = original, gate
    def create_module(self, spec):
        return self.original.create_module(spec) if hasattr(self.original,'create_module') else None
    def exec_module(self, module):
        self.original.exec_module(module)
        self.gate.patch(module)
    def __getattr__(self, name):
        return getattr(self.original, name)

class LoaderGate(importlib.abc.MetaPathFinder):
    watched = {'torch','torch.serialization','torch.hub','safetensors.torch','huggingface_hub','huggingface_hub.file_download','huggingface_hub._snapshot_download'}
    def __init__(self, pins):
        self.pins, self.bindings, self.originals = pins, {}, {}
        self.active = False
        self.socket_originals = {}
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.watched:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        require(spec is not None and spec.loader is not None, 'PIN_IMPORT_SPEC_UNAVAILABLE:' + fullname, 'BLOCKED_BY_LOADER_COVERAGE')
        spec.loader = _AfterExec(spec.loader, self)
        return spec
    def install(self):
        self.active = True
        sys.meta_path.insert(0,self)
        self.socket_originals = {'connect':socket.socket.connect,'create_connection':socket.create_connection}
        gate = self
        def connect(sock,address):
            if sock.family in (socket.AF_INET,socket.AF_INET6):
                return gate.deny(address)
            return gate.socket_originals['connect'](sock,address)
        self.connect_wrapper = connect
        socket.socket.connect = connect
        socket.create_connection = self.deny
    def deny(self, *args, **kwargs):
        self.pins.event('network_or_cache_fallback_rejected', requested=str(args[:2]))
        raise PinError('DOWNLOAD_OR_CACHE_FALLBACK_FORBIDDEN', 'BLOCKED_BY_LOADER_COVERAGE')
    def bind(self, module, attr, kind):
        if attr not in module.__dict__:
            return
        old = module.__dict__[attr]
        if getattr(old, '_runtime_pin_owner', None) is self:
            wrapped = old
        else:
            @functools.wraps(old)
            def wrapped(*args, **kwargs):
                self.assert_integrity()
                if kind in ('torch.load','safetensors.torch.load_file'):
                    return self.pins.boundary(kind,old,*args,**kwargs)
                if kind == 'deny':
                    return self.deny(*args,**kwargs)
                return self.cached_call(kind,old,args,kwargs)
            wrapped._runtime_pin_owner = self
        key = (module.__name__,attr)
        self.originals[key] = old
        self.bindings[key] = wrapped
        setattr(module,attr,wrapped)
    def patch(self, module):
        name = module.__name__
        if name in ('torch','torch.serialization'):
            self.bind(module,'load','torch.load')
        elif name == 'safetensors.torch':
            self.bind(module,'load_file','safetensors.torch.load_file')
        elif name == 'torch.hub':
            self.bind(module,'load_state_dict_from_url','torch.hub.cached')
            self.bind(module,'load','torch.hub.local_repo')
            self.bind(module,'download_url_to_file','deny')
        elif name in ('huggingface_hub','huggingface_hub.file_download'):
            self.bind(module,'hf_hub_download','hf.cached')
            self.bind(module,'snapshot_download','deny')
        elif name == 'huggingface_hub._snapshot_download':
            self.bind(module,'snapshot_download','deny')
        self.pins.event('loader_module_hooked',module=name,attributes=[attr for mod,attr in self.bindings if mod==name])
    def assert_integrity(self):
        require(self.active and self in sys.meta_path, 'IMPORT_GUARD_DISABLED', 'BLOCKED_BY_LOADER_COVERAGE')
        require(socket.socket.connect is self.connect_wrapper and getattr(socket.create_connection,'__self__',None) is self, 'NETWORK_GUARD_DISABLED', 'BLOCKED_BY_LOADER_COVERAGE')
        for (name, attr), wrapper in self.bindings.items():
            module = sys.modules.get(name)
            require(module is not None and module.__dict__.get(attr) is wrapper, 'LOADER_CHECKER_DISABLED:' + name + '.' + attr, 'BLOCKED_BY_LOADER_COVERAGE')
    def cached_call(self, kind, old, args, kwargs):
        p = self.pins
        p.assert_manifest();p.check_environment();p.check_revision()
        bound = inspect.signature(old).bind(*args,**kwargs)
        bound.apply_defaults()
        a = bound.arguments
        if kind == 'torch.hub.cached':
            record = next((r for r in p.weights.values() if r.get('url')==a.get('url')),None)
            require(record is not None, 'UNAPPROVED_HUB_WEIGHT_URL', 'BLOCKED_BY_LOADER_COVERAGE')
            expected = native(record)
            model_dir = a.get('model_dir')
            require(model_dir is None or identity(model_dir)==identity(expected.parent), 'HUB_CACHE_DIRECTORY_CHANGED', 'BLOCKED_BY_LOADER_COVERAGE')
            require(a.get('file_name') in (None,expected.name), 'HUB_CACHE_FILENAME_CHANGED', 'BLOCKED_BY_LOADER_COVERAGE')
            p.checked_file(record)
        elif kind == 'torch.hub.local_repo':
            model = a.get('model');repo = a.get('repo_or_dir')
            require(model in p.spec['hub_models'] and a.get('source')=='local' and identity(repo)==identity(p.spec['hub_models'][model]), 'NONLOCAL_OR_UNAPPROVED_HUB_SOURCE', 'BLOCKED_BY_LOADER_COVERAGE')
        elif kind == 'hf.cached':
            hf = p.spec['hf']
            require(a.get('repo_id')==hf['repo_id'] and a.get('filename')==hf['filename'] and a.get('revision') in (None,'main',hf['revision']) and not a.get('force_download') and not a.get('subfolder'), 'HF_FALLBACK_OR_REVISION_FORBIDDEN', 'BLOCKED_BY_LOADER_COVERAGE')
            require(a.get('cache_dir') in (None,str(Path(p.spec['environment']['HF_HOME'])/'hub')), 'HF_CACHE_ROOT_CHANGED', 'BLOCKED_BY_LOADER_COVERAGE')
            p.checked_file(p.weights[hf['weight_id']])
        else:
            raise PinError('UNKNOWN_GUARDED_CACHE_LOADER', 'BLOCKED_BY_LOADER_COVERAGE')
        result = old(*args,**kwargs)
        if kind == 'hf.cached':
            p.checked_file(p.weights[p.spec['hf']['weight_id']],request=result)
        return result
    def close(self):
        for (name, attr), old in reversed(list(self.originals.items())):
            module = sys.modules.get(name)
            if module is not None:
                setattr(module,attr,old)
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        if self.socket_originals:
            socket.socket.connect=self.socket_originals['connect']
            socket.create_connection=self.socket_originals['create_connection']
        self.active=False


def record_prelaunch_failure(root, entry, exc):
    import uuid
    payload=dict(status=getattr(exc,'code','BLOCKED_BY_RUNTIME_MANIFEST'),reasons=getattr(exc,'reasons',[str(exc)]),entry=entry,error=str(exc),traceback=traceback.format_exc(),finished_unix=time.time(),exit_code=2,terminal=True,model_process_started=False,model_dependencies_imported=False,formal_result_created=False,model_attempt_created=False)
    folder=Path(root)/'logs/prelaunch_failures';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(entry+'_'+str(uuid.uuid4())+'.json')).open('x',encoding='utf-8') as f:
        json.dump(payload,f,indent=2)
    return payload

def static_entry(root):
    # Host performs file checks in the actual WSL filesystem; no model or CUDA entry.
    if os.name == 'nt':
        import subprocess
        r=Path(root).resolve();linux='/mnt/'+str(r)[0].lower()+str(r)[2:].replace('\\','/')
        command=['wsl.exe','-d','Ubuntu','--','env','PYTHONDONTWRITEBYTECODE=1','/home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python','-B',linux+'/scripts/runtime_dependency_pins.py','--static-only','--root',linux]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60)
        require(result.returncode==0,'WSL_STATIC_PIN_REFUSED:'+result.stdout+result.stderr,'BLOCKED_BY_WEIGHT_PIN')
        return json.loads(result.stdout)
    return RuntimePins(root).static_check()

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--static-only',action='store_true',required=True);parser.add_argument('--root',required=True);a=parser.parse_args()
    try:
        print(json.dumps(static_entry(a.root)),flush=True)
    except BaseException as exc:
        print(json.dumps(dict(status=getattr(exc,'code','BLOCKED_BY_RUNTIME_MANIFEST'),error=str(exc),traceback=traceback.format_exc(),model_started=False)),flush=True)
        sys.exit(2)
