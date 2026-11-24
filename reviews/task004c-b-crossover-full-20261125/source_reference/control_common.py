"""Small, dependency-light integrity and resource helpers."""
import hashlib, json, os, pathlib, shutil, time
GIB = 1024 ** 3
BASELINE_COMMIT = 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'
class ControlError(RuntimeError): pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def require_space(path, required_bytes=0, floor_bytes=10*GIB, free_bytes=None):
    p=pathlib.Path(path)
    while not p.exists(): p=p.parent
    free=shutil.disk_usage(p).free if free_bytes is None else free_bytes
    if free < floor_bytes + required_bytes:
        raise ControlError('STORAGE_BLOCKED: free=%d required=%d floor=%d'%(free,required_bytes,floor_bytes))
    return free

def exclusive_json(path, data):
    p=pathlib.Path(path)
    with p.open('xb') as f:
        f.write(canonical(data)+b'\n');f.flush();os.fsync(f.fileno())
def verify_pins(pins):
    result={}
    for name, expected in pins.items():
        p=pathlib.Path(name)
        if not p.is_file() or p.is_symlink(): raise ControlError('Missing/linked identity file: '+name)
        actual=file_sha(p)
        if actual!=expected: raise ControlError('Identity SHA mismatch: '+name)
        result[name]=actual
    return result
