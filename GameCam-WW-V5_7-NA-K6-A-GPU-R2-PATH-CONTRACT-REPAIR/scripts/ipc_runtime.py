"""Session-owned POSIX Arena paths. Process-local adaptation, never an OS sandbox."""
import hashlib,json,os,pathlib,re,stat,sys,tempfile,time
BASE=pathlib.Path('/dev/shm/gamecam-ipc')
SID=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{7,95}\Z')
MARKER='.gamecam-session.json'
class IPCError(RuntimeError):pass
class EventLog(list):
    def __init__(self,path):super().__init__();self.path=pathlib.Path(path)
    def append(self,event):
        super().append(event)
        fd=os.open(str(self.path), os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'a',encoding='utf-8') as f:
                f.write(json.dumps(event)+'\n')
        except BaseException:
            try: os.close(fd)
            except OSError: pass
            raise


def emit(events,name,**data):
    record={'event':name,'pid':os.getpid(),'unix_time':time.time(),**data};events.append(record);return record

def exact_directory(path,mode=0o700):
    p=pathlib.Path(path)
    if not p.is_absolute() or '..' in p.parts or p.resolve(strict=True)!=p:raise IPCError('IPC_PATH_NOT_EXACT:'+str(p))
    s=p.lstat()
    if not stat.S_ISDIR(s.st_mode) or stat.S_IMODE(s.st_mode)!=mode or s.st_uid!=os.getuid():raise IPCError('IPC_DIRECTORY_IDENTITY:'+str(p))
    return s

def expected_root(session):
    if not isinstance(session,str) or not SID.fullmatch(session):raise IPCError('IPC_SESSION_FORMAT')
    return BASE/session

def prepare_owner(session_dir,session):
    """Owning supervisor only, after authorization claim and before worker creation."""
    session_dir=pathlib.Path(session_dir).resolve(strict=True);events=EventLog(session_dir/'ipc_owner_events.jsonl');root=expected_root(session)
    if BASE.is_symlink():raise IPCError('IPC_BASE_SYMLINK')
    try:BASE.mkdir(mode=0o700)
    except FileExistsError:pass
    exact_directory(BASE)
    root.mkdir(mode=0o700,exist_ok=False);s=exact_directory(root)
    fallback=session_dir/'tmp';fallback_created=False;marker_created=False
    try:
        fallback.mkdir(mode=0o700,exist_ok=False);fallback_created=True;fs=exact_directory(fallback)
        binding={'session':session,'owner_uid':os.getuid(),'supervisor_pid':os.getpid(),'session_dir':str(session_dir),'ipc_root':str(root),'root_dev':s.st_dev,'root_ino':s.st_ino,'fallback_dev':fs.st_dev,'fallback_ino':fs.st_ino}
        fd=os.open(root/MARKER,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);marker_created=True
        with os.fdopen(fd,'w') as f:json.dump(binding,f)
        emit(events,'IPC_ROOT_CREATED',root=str(root),fallback=str(fallback),owner_uid=os.getuid(),mode='0700',root_dev=s.st_dev,root_ino=s.st_ino)
        return {'binding':binding,'root':str(root),'fallback':str(fallback),'events':events}
    except BaseException as exc:
        # No worker exists yet. Remove only entries created in this setup operation.
        errors=[]
        try:
            current=exact_directory(root)
            if (current.st_dev,current.st_ino)!=(s.st_dev,s.st_ino):raise IPCError('IPC_SETUP_ROOT_REPLACED')
            if marker_created:(root/MARKER).unlink()
            root.rmdir()
        except OSError as cleanup:errors.append(str(cleanup))
        except IPCError as cleanup:errors.append(str(cleanup))
        if fallback_created:
            try:exact_directory(fallback);fallback.rmdir()
            except (OSError,IPCError) as cleanup:errors.append(str(cleanup))
        emit(events,'IPC_ROOT_SETUP_FAILED',error=str(exc),root_removed=not root.exists(),cleanup_errors=errors)
        raise

class IPCPolicy:
    def __init__(self,root,fallback,session,session_dir):
        self.root=pathlib.Path(root);self.fallback=pathlib.Path(fallback);self.session=session;self.session_dir=pathlib.Path(session_dir).resolve(strict=True);self.events=EventLog(self.session_dir/'ipc_worker_events.jsonl')
        if self.root!=expected_root(session) or self.fallback!=self.session_dir/'tmp':raise IPCError('IPC_SESSION_PATH_BINDING')
        exact_directory(self.root);exact_directory(self.fallback)
        self.binding=json.loads((self.root/MARKER).read_text())
        if self.binding['session']!=session or self.binding['session_dir']!=str(self.session_dir) or self.binding['owner_uid']!=os.getuid():raise IPCError('IPC_BINDING_MISMATCH')
        self.verify()
        self.original_candidates=None;self.original_choose=None;self.installed=False
    def verify(self):
        s=exact_directory(self.root);exact_directory(self.fallback)
        if (s.st_dev,s.st_ino)!=(self.binding['root_dev'],self.binding['root_ino']):raise IPCError('IPC_ROOT_REPLACED')
        fs=self.fallback.stat()
        if (fs.st_dev,fs.st_ino)!=(self.binding['fallback_dev'],self.binding['fallback_ino']):raise IPCError('IPC_FALLBACK_REPLACED')
    def is_ipc_path(self,path):
        p=pathlib.Path(os.path.abspath(path))
        return p.is_relative_to(BASE) or (p.parent==self.fallback and p.name.startswith('pym-'))
    def check_file(self,path,write=False,operation='open',flags=None):
        p=pathlib.Path(os.path.abspath(path))
        try:
            self.verify()
            if p.resolve(strict=False)!=p:raise IPCError('IPC_SYMLINK_ESCAPE')
            if p==self.root/MARKER and not write and operation=='open':return True
            if operation not in ('open','os.remove'):raise IPCError('IPC_OPERATION_NOT_ARENA_OPEN_OR_UNLINK')
            if p.parent not in (self.root,self.fallback):raise IPCError('IPC_FOREIGN_SESSION_OR_NESTED_PATH')
            if not re.fullmatch(r'pym-'+str(os.getpid())+r'-[a-z0-9_]{8}',p.name):raise IPCError('IPC_FILENAME_OR_PID')
            if p.exists():
                s=p.lstat()
                if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600:raise IPCError('IPC_FILE_IDENTITY')
            elif write and operation=='open' and (not isinstance(flags,int) or not flags&os.O_CREAT or not flags&os.O_EXCL):raise IPCError('IPC_CREATION_REQUIRES_EXCLUSIVE_0600_MKSTEMP')
            emit(self.events,'IPC_WRITE_ALLOWED' if write else 'IPC_READ_ALLOWED',path=str(p),operation=operation,policy_decision=True)
            return True
        except (IPCError,OSError) as e:
            emit(self.events,'IPC_WRITE_DENIED' if write else 'IPC_READ_DENIED',path=str(p),operation=operation,reason=str(e));raise IPCError(str(e)) from e
    def file_unlinked(self,path):emit(self.events,'IPC_FILE_CLEANED',path=str(path),operation='unlink audit event; syscall outcome not independently guaranteed')
    def install_arena(self,force_fallback=False):
        """Executed only inside this worker; stdlib files and other processes are untouched."""
        import multiprocessing.heap as heap
        self.verify()
        # Existing arenas would preserve the old directory and invalidate first-allocation proof.
        if heap.BufferWrapper._heap._arenas:raise IPCError('IPC_ARENA_ALREADY_ALLOCATED')
        self.original_candidates=list(heap.Arena._dir_candidates);self.original_choose=heap.Arena._choose_dir
        policy=self
        def choose(arena,size):
            policy.verify()
            try:
                st=os.statvfs(policy.root);enough=st.f_bavail*st.f_frsize>=size
            except OSError:enough=False
            target=policy.root if enough and not force_fallback else policy.fallback
            emit(policy.events,'IPC_ARENA_DIRECTORY_SELECTED',path=str(target),size=size,forced_fallback=force_fallback,shared_memory_space_sufficient=enough)
            return str(target)
        heap.Arena._dir_candidates=[str(self.root)];heap.Arena._choose_dir=choose
        os.environ['TMPDIR']=str(self.fallback);tempfile.tempdir=str(self.fallback)
        self.installed=True;emit(self.events,'IPC_PROCESS_LOCAL_ARENA_INSTALLED',root=str(self.root),fallback=str(self.fallback),python=sys.version,stdlib_files_modified=False)

def cleanup_owner(owner,worker_exited,monitor_exited,owned_pids=()):
    events=owner['events'];b=owner['binding'];root=pathlib.Path(owner['root'])
    if not worker_exited or not monitor_exited:raise IPCError('IPC_CLEANUP_BEFORE_CHILD_EXIT')
    if b['supervisor_pid']!=os.getpid():raise IPCError('IPC_CLEANUP_NOT_OWNER')
    s=exact_directory(root)
    if (s.st_dev,s.st_ino)!=(b['root_dev'],b['root_ino']):raise IPCError('IPC_CLEANUP_ROOT_REPLACED')
    allowed={int(pid) for pid in owned_pids if pid is not None};allowed.add(os.getpid())
    fallback=pathlib.Path(owner['fallback']);fs=exact_directory(fallback)
    if str(fallback)!=str(pathlib.Path(b['session_dir'])/'tmp') or (fs.st_dev,fs.st_ino)!=(b['fallback_dev'],b['fallback_ino']):raise IPCError('IPC_CLEANUP_FALLBACK_REPLACED')
    entries=list(root.iterdir());fallback_entries=list(fallback.iterdir())
    for p in entries+fallback_entries:
        if p==root/MARKER:continue
        m=re.fullmatch(r'pym-(\d+)-[a-z0-9_]{8}',p.name)
        st=p.lstat()
        if not m or int(m.group(1)) not in allowed or not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600:raise IPCError('IPC_CLEANUP_FOREIGN_RESIDUAL:'+str(p))
    # Validate all entries before unlinking anything. No recursive deletion or symlink traversal.
    for p in entries+fallback_entries:
        p.unlink();emit(events,'IPC_FILE_CLEANED',path=str(p),cleanup_owner=True)
    root.rmdir();emit(events,'IPC_ROOT_REMOVED',root=str(root))
    return {'passed':True,'root_removed':not root.exists(),'fallback_empty':not list(fallback.iterdir()),'events':events,'worker_exited_before_cleanup':worker_exited,'monitor_exited_before_cleanup':monitor_exited,'recursive_delete_used':False}

def verify_runtime_contract(record):
    p=pathlib.Path(record['path']);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise IPCError('IPC_CONTRACT_SHA_DRIFT')
    c=json.loads(raw)
    if list(sys.version_info[:3])!=c['python_version']:raise IPCError('IPC_PYTHON_VERSION_DRIFT')
    for row in c['stdlib_files'].values():
        if hashlib.sha256(pathlib.Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise IPCError('IPC_STDLIB_SHA_DRIFT')
    return c
