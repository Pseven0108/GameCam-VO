"""Attempt-owned output lifecycle only; no tensors, RNG or optimization imports."""
import hashlib,json,os,pathlib,stat
SCHEMA='GAMECAM_IO_OWNER_V1'
class OutputOwnershipError(RuntimeError):pass

def _unlinked(path):
    path=pathlib.Path(path)
    if not path.is_absolute() or path.absolute()!=path:
        raise OutputOwnershipError('Absolute normalized path required')
    for p in (path,*path.parents):
        if p.is_symlink():raise OutputOwnershipError('Symlink in output path')
    if path.resolve()!=path:raise OutputOwnershipError('Output path not canonical')
    return path

def _directory(path):
    path=_unlinked(path);s=path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid():
        raise OutputOwnershipError('Directory type/uid ownership mismatch')
    return s

def _context(out):
    out=_unlinked(out);s=_directory(out)
    root=_unlinked(pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE']))
    mode=os.environ['GAMECAM_NATIVE_APPROVED_MODE']
    if out!=root/'attempts'/mode or pathlib.Path(os.environ['GAMECAM_NATIVE_ATTEMPT'])!=out:
        raise OutputOwnershipError('Attempt escaped this stage namespace')
    p=out/'LAUNCH_INTENT.json'
    if p.is_symlink() or not p.is_file() or p.stat().st_uid!=s.st_uid:
        raise OutputOwnershipError('Attempt intent missing or wrong owner')
    intent=json.loads(p.read_text())
    token=os.environ['GAMECAM_NATIVE_INTERNAL_CHILD']
    if intent['mode']!=mode or intent['child_token']!=token:
        raise OutputOwnershipError('Run ID / stage ownership mismatch')
    if (out/'PROCESS_RECEIPT.json').exists() or (out/'SUCCESS.json').exists():
        raise OutputOwnershipError('Completed/failed attempt cannot be reused')
    return {'schema':SCHEMA,'attempt':str(out),'run_id_sha256':hashlib.sha256(token.encode()).hexdigest(),
            'mode':mode,'uid':s.st_uid,'attempt_dev':s.st_dev,'attempt_ino':s.st_ino}

def _owner_file(native):return pathlib.Path(native)/'.gamecam_io_owner.json'

def validate_native(out,native):
    expected=_context(out);native=_unlinked(native)
    if native!=pathlib.Path(out)/'native':raise OutputOwnershipError('scene=native containment mismatch')
    s=_directory(native);p=_owner_file(native)
    if p.is_symlink() or not p.is_file() or p.stat().st_uid!=expected['uid']:
        raise OutputOwnershipError('Native ownership receipt absent or unsafe')
    actual=json.loads(p.read_text())
    expected.update(native_dev=s.st_dev,native_ino=s.st_ino,creator='IO_COMPAT_OVERLAY')
    if actual!=expected:raise OutputOwnershipError('Native directory owner/run/inode differs')
    for child in native.rglob('*'):
        if child.is_symlink() or child.lstat().st_uid!=expected['uid']:
            raise OutputOwnershipError('Unsafe nested service entry')
    return native

def prepare_native(out):
    expected=_context(out);native=pathlib.Path(out)/'native'
    native.mkdir(mode=0o700,parents=False,exist_ok=False)
    s=_directory(native);expected.update(native_dev=s.st_dev,native_ino=s.st_ino,creator='IO_COMPAT_OVERLAY')
    p=_owner_file(native)
    with p.open('x',encoding='utf-8') as f:json.dump(expected,f,sort_keys=True)
    return validate_native(out,native)

def prepare_summary_writer(out,writer_class):
    """Overlay owns mkdir; the real writer receives an already-validated path."""
    native=prepare_native(out)
    writer=writer_class(str(native))
    validate_native(out,native)
    return writer

def validate_rebound_output(bundle,out):
    tracker=bundle['tracker']
    if tracker.cfg['scene']!='native':raise OutputOwnershipError('Frozen R2 scene must be native')
    native=validate_native(out,pathlib.Path(tracker.output))
    if pathlib.Path(tracker.video.output)!=native or pathlib.Path(tracker.motion_filter.save_dir)!=native or pathlib.Path(tracker.online_ba.output)!=native or pathlib.Path(tracker.frontend.loop_closing.output)!=native:
        raise OutputOwnershipError('Rebound diagnostic destinations disagree')
    return native
