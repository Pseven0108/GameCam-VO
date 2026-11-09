"""Pinned source imports, including the direct-spec path used by Torch Hub.

Only manifest-listed .py files are executable. No bytecode reads or writes.
The byte buffer checked by SHA256 is the buffer passed to source_to_code.
"""
import hashlib, importlib.abc, importlib.machinery, importlib.util
import importlib._bootstrap as _bootstrap
import os, pathlib, stat, sys, time

class SourceIdentityError(RuntimeError):
    pass

class VerifiedDynamicSourceLoader(importlib.machinery.SourceFileLoader):
    def __init__(self, fullname, filename, record, owner):
        super().__init__(fullname, filename)
        self.record, self.owner = record, owner
    def get_data(self, path):
        if path != self.path:
            raise SourceIdentityError('DYNAMIC_SOURCE_DATA_PATH_REJECTED:'+str(path))
        return self.owner.read_verified(path, self.record, self.name)
    def get_code(self, fullname):
        if fullname != self.name:
            raise SourceIdentityError('DYNAMIC_SOURCE_NAME_MISMATCH')
        data = self.get_data(self.path)
        return self.source_to_code(data, self.path)
    def get_source(self, fullname):
        if fullname != self.name:
            raise SourceIdentityError('DYNAMIC_SOURCE_NAME_MISMATCH')
        return importlib.util.decode_source(self.get_data(self.path))
    def set_data(self, *args, **kwargs):
        raise SourceIdentityError('DYNAMIC_BYTECODE_WRITE_FORBIDDEN')
    def exec_module(self, module):
        start=time.monotonic()
        self.owner.event('source_import_started', self.name, self.path)
        try:
            super().exec_module(module)
        except BaseException as exc:
            self.owner.event('source_import_rejected',self.name,self.path,start=start,decision='DENY',reason=str(exc))
            raise
        self.owner.event('source_import_completed',self.name,self.path,start=start)

class VerifiedSourceFinder(importlib.abc.MetaPathFinder):
    def __init__(self, source_root, source_records, external_records=(), candidate_sha256=None, event_sink=None):
        root=pathlib.Path(source_root)
        if not root.is_absolute() or root.resolve()!=root:
            raise SourceIdentityError('SOURCE_ROOT_NOT_CANONICAL')
        self.root=root;self.events=[];self.candidate_sha256=candidate_sha256;self.event_sink=event_sink
        self.records={}
        for r in source_records:
            rp=pathlib.PurePath(r['path'])
            if rp.is_absolute() or '..' in rp.parts:raise SourceIdentityError('SOURCE_RECORD_TRAVERSAL')
            if rp.suffix=='.py':self._record(root/rp,r)
        external_roots=set()
        for r in external_records:
            p=pathlib.Path(r['path'])
            if p.suffix=='.py':
                # The base candidate also pins the torch_scatter build source; it
                # retains exact-file source checks, but never gains a Hub entry.
                marker='/baselines/droid_w/prior_sources/'
                if marker not in str(p):raise SourceIdentityError('UNAPPROVED_EXTERNAL_SOURCE_ROOT')
                head,tail=str(p).split(marker,1);repo=tail.split('/',1)[0]
                if repo not in ('Metric3D','FiT3D','pytorch_scatter'):raise SourceIdentityError('UNAPPROVED_EXTERNAL_PRIOR')
                external_roots.add(pathlib.Path(head+marker+repo));self._record(p,r)
        self.roots=(root,)+tuple(sorted(external_roots));self.hub_binding=None
        self.identities={p:r['sha256'] for p,r in self.records.items()}
    def _record(self,p,r):
        if not p.is_absolute() or '..' in p.parts:raise SourceIdentityError('SOURCE_RECORD_INVALID_PATH')
        h=r.get('sha256')
        if not isinstance(h,str) or len(h)!=64 or any(x not in '0123456789abcdef' for x in h):raise SourceIdentityError('SOURCE_RECORD_INVALID_SHA')
        old=self.records.get(str(p))
        if old and old['sha256']!=h:raise SourceIdentityError('CONFLICTING_SOURCE_IDENTITIES')
        self.records[str(p)]=dict(r,path=str(p))
    def event(self,event,name,path,start=None,decision='ALLOW',reason=None,**extra):
        now=time.monotonic();r=self.records.get(str(path),{})
        row=dict(event=event,module=name,path=str(path),real_path=str(path),candidate_sha256=self.candidate_sha256,sha256=r.get('sha256'),loader='VerifiedDynamicSourceLoader',unix_time=time.time(),monotonic_time=now,elapsed_seconds=None if start is None else now-start,decision=decision,reason=reason,**extra)
        self.events.append(row)
        if self.event_sink:self.event_sink(row)
        return row
    def checked_path(self,path):
        p=pathlib.Path(path)
        if not p.is_absolute() or '..' in p.parts:raise SourceIdentityError('DYNAMIC_SOURCE_TRAVERSAL_OR_RELATIVE')
        if p.suffix!='.py':raise SourceIdentityError('DYNAMIC_SOURCE_ONLY_PY')
        if not any(p.is_relative_to(root) for root in self.roots):raise SourceIdentityError('DYNAMIC_SOURCE_OUTSIDE_ROOT')
        if str(p) not in self.records:raise SourceIdentityError('DYNAMIC_SOURCE_NOT_REGISTERED:'+str(p))
        if p.resolve()!=p or p.is_symlink():raise SourceIdentityError('DYNAMIC_SOURCE_SYMLINK_FORBIDDEN:'+str(p))
        return p,self.records[str(p)]
    def read_verified(self,path,record,name):
        p,r=self.checked_path(path)
        if r['sha256']!=record['sha256']:raise SourceIdentityError('DYNAMIC_SOURCE_RECORD_CHANGED')
        # Audit-approved pathname; O_NOFOLLOW protects the leaf. Verify the
        # kernel descriptor target before reading to detect a parent-dir race.
        leaf=os.open(str(p),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode):raise SourceIdentityError('DYNAMIC_SOURCE_NOT_REGULAR')
            if pathlib.Path(os.path.realpath('/proc/self/fd/'+str(leaf)))!=p:raise SourceIdentityError('DYNAMIC_SOURCE_DESCRIPTOR_ESCAPE')
            data=bytearray()
            while True:
                b=os.read(leaf,1024*1024)
                if not b:break
                data.extend(b)
                if len(data)>64*1024*1024:raise SourceIdentityError('DYNAMIC_SOURCE_SIZE_LIMIT')
            after=os.fstat(leaf)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise SourceIdentityError('DYNAMIC_SOURCE_CHANGED_DURING_READ')
            if pathlib.Path(os.path.realpath('/proc/self/fd/'+str(leaf)))!=p:raise SourceIdentityError('DYNAMIC_SOURCE_REPLACED_DURING_READ')
        finally:os.close(leaf)
        data=bytes(data);actual=hashlib.sha256(data).hexdigest()
        if actual!=r['sha256']:raise SourceIdentityError('IMPORT_SOURCE_SHA_DRIFT:'+str(p))
        self.event('source_bytes_verified',name,p,bytes=len(data),strategy='VERIFIED_SOURCE_ONLY',device=before.st_dev,inode=before.st_ino)
        return data
    def spec(self,name,path):
        try:p,r=self.checked_path(path)
        except BaseException as exc:
            self.event('source_spec_rejected',name,str(path),decision='DENY',reason=str(exc));raise
        loader=VerifiedDynamicSourceLoader(name,str(p),r,self)
        return importlib.util.spec_from_file_location(name,str(p),loader=loader,submodule_search_locations=[str(p.parent)] if p.name=='__init__.py' else None)
    def find_spec(self,fullname,path=None,target=None):
        spec=importlib.machinery.PathFinder.find_spec(fullname,path,target)
        if spec is None or not isinstance(spec.loader,importlib.machinery.SourceFileLoader):return None
        p=pathlib.Path(spec.origin).absolute()
        if p.resolve()!=p and str(p.resolve()) in self.records:raise SourceIdentityError('IMPORT_SOURCE_SYMLINK_FORBIDDEN:'+str(p))
        if str(p) not in self.records:
            if any(p.is_relative_to(root) for root in self.roots):raise SourceIdentityError('DYNAMIC_SOURCE_NOT_REGISTERED:'+str(p))
            return None
        return self.spec(fullname,p)
    def install(self):
        if any(isinstance(x,VerifiedSourceFinder) for x in sys.meta_path):raise SourceIdentityError('VERIFIED_SOURCE_FINDER_ALREADY_INSTALLED')
        sys.meta_path.insert(0,self);return self
    def load_dynamic(self,name,path,temporary=False):
        # Use the interpreter module lock for the pinned Python environment.
        # Ordinary imports retain Python's native import machinery and cache.
        with _bootstrap._ModuleLockManager(name):
            spec=self.spec(name,path);missing=object();previous=sys.modules.get(name,missing)
            if not temporary and previous is not missing:
                if getattr(getattr(previous,'__spec__',None),'origin',None)!=spec.origin:raise SourceIdentityError('DYNAMIC_MODULE_NAME_COLLISION')
                return previous
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module
            try:spec.loader.exec_module(module)
            except BaseException:
                if previous is missing:sys.modules.pop(name,None)
                else:sys.modules[name]=previous
                raise
            if temporary:
                if previous is missing:sys.modules.pop(name,None)
                else:sys.modules[name]=previous
            elif '.' in name:
                parent,_,child=name.rpartition('.')
                if parent in sys.modules:setattr(sys.modules[parent],child,module)
            return module
    def bind_torch_hub(self,hub,entrypoints,after_source_import=None):
        if self.hub_binding is not None:raise SourceIdentityError('TORCH_HUB_ALREADY_BOUND')
        approved={}
        for entry in entrypoints:
            lexical=pathlib.Path(entry['requested_path']);canonical=pathlib.Path(entry['real_path'])
            self.checked_path(canonical)
            if '..' in lexical.parts or not lexical.is_absolute() or lexical.name!='hubconf.py':raise SourceIdentityError('UNAPPROVED_HUB_ENTRY')
            if lexical.resolve()!=canonical:raise SourceIdentityError('HUB_ENTRY_ALIAS_IDENTITY_DRIFT')
            approved[str(lexical)]=str(canonical);approved[str(canonical)]=str(canonical)
        original=hub._import_module
        def verified_hub_import(name,path):
            lexical=pathlib.Path(path)
            try:
                if '..' in lexical.parts or str(lexical) not in approved:raise SourceIdentityError('UNAPPROVED_HUB_DYNAMIC_PATH:'+str(path))
                real=approved[str(lexical)]
                if lexical.resolve()!=pathlib.Path(real):raise SourceIdentityError('HUB_ENTRY_ALIAS_IDENTITY_DRIFT')
                # Torch Hub originally creates a fresh module without persistent
                # sys.modules registration. Temporary registration permits normal
                # cycles during execution, then restores that Hub behavior.
                # _load_local temporarily puts the historical alias on sys.path.
                # Use the frozen canonical parent for this source execution so
                # normal submodules cannot inherit that alias as their origin.
                parent=str(pathlib.Path(real).parent)
                with _bootstrap._ModuleLockManager(name):
                    sys.path.insert(0,parent)
                    try:
                        module=self.load_dynamic(name,real,temporary=True)
                        if after_source_import:after_source_import(module,real)
                        return module
                    finally:sys.path.remove(parent)
            except BaseException as exc:
                self.event('hub_import_rejected',name,str(path),decision='DENY',reason=str(exc));raise
        hub._import_module=verified_hub_import;self.hub_binding=(hub,original,verified_hub_import)
        self.event('torch_hub_adapter_installed','torch.hub','',scope='Only exact pinned Metric3D/FiT3D hubconf entries; all other direct Hub imports denied')
        return self
    def restore_torch_hub(self):
        if self.hub_binding:
            hub,original,wrapper=self.hub_binding
            if hub._import_module is not wrapper:raise SourceIdentityError('TORCH_HUB_BINDING_DRIFT')
            hub._import_module=original;self.hub_binding=None
