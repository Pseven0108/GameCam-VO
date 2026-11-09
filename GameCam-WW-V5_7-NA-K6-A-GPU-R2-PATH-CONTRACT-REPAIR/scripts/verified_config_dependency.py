"""Exact dependency-path repair for the frozen Metric3D config, no file edits."""
import hashlib,pathlib
class VerifiedConfigDependency:
    def __init__(self,source_finder,policy,event_sink=None):
        self.finder=source_finder;self.policy=policy;self.event_sink=event_sink;self.events=[];self.binding=None
        assert policy['schema']=='gamecam-prior-factory-cpu-policy-v1'
    def event(self,kind,**kw):
        row=dict(event=kind,**kw);self.events.append(row)
        if self.event_sink:self.event_sink(row)
    def _verify(self,root,rel,expected):
        relative=pathlib.PurePosixPath(rel)
        if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('CONFIG_DEPENDENCY_PATH_ESCAPE')
        p=root/rel;canonical,record=self.finder.checked_path(p)
        if record['sha256']!=expected:raise RuntimeError('CONFIG_DEPENDENCY_MANIFEST_SHA_DRIFT:'+str(p))
        data=self.finder.read_verified(str(p),record,'config:'+rel)
        if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError('CONFIG_DEPENDENCY_SOURCE_SHA_DRIFT')
        return canonical
    def on_hub_import(self,module,source_path):
        p=pathlib.Path(source_path)
        if p.parent.name!='Metric3D':return
        root=p.parent;Config=module.Config
        if self.binding:
            if self.binding[0] is not Config or Config._get_cfg_path is not self.binding[3] or Config.fromfile is not self.binding[4]:raise RuntimeError('CONFIG_DEPENDENCY_BINDING_DRIFT')
            return
        original_get=Config.__dict__['_get_cfg_path'];original_from=Config.__dict__['fromfile'];get=Config._get_cfg_path;fromfile=Config.fromfile
        closure=self.policy['metric3d_config_sources'];edges=self.policy['metric3d_config_edges'];entry=self.policy['metric3d_entry_config']
        def checked_fromfile(filename,*args,**kwargs):
            requested=pathlib.Path(filename)
            if not requested.is_absolute() or '..' in requested.parts or requested!=root/entry or requested.resolve()!=requested:raise RuntimeError('CONFIG_ENTRY_NOT_ALLOWLISTED:'+str(filename))
            for r in closure:self._verify(root,r['relative_path'],r['sha256'])
            try:return fromfile(str(root/entry),*args,**kwargs)
            finally:
                for r in closure:self._verify(root,r['relative_path'],r['sha256'])
        def checked_get(cfg_path,filename):
            declaring=pathlib.Path(filename)
            if not declaring.is_absolute() or '..' in declaring.parts or declaring.resolve()!=declaring:raise RuntimeError('CONFIG_DECLARING_PATH_ESCAPE')
            matches=[e for e in edges if root/e['declaring_relative_path']==declaring and e['requested_relative_path']==cfg_path]
            if len(matches)!=1:
                self.event('CONFIG_DEPENDENCY_REJECTED',requested=str(cfg_path),declaring=str(filename))
                raise RuntimeError('CONFIG_DEPENDENCY_NOT_ALLOWLISTED:'+str(cfg_path))
            e=matches[0];target=self._verify(root,e['target_relative_path'],e['sha256'])
            self.event('CONFIG_DEPENDENCY_RESOLVED',requested=cfg_path,declaring=str(declaring),target=str(target),sha256=e['sha256'],path_repaired=e.get('path_repaired',False))
            return str(target),None
        checked_get.__wrapped__=get;checked_fromfile.__wrapped__=fromfile
        Config._get_cfg_path=staticmethod(checked_get);Config.fromfile=staticmethod(checked_fromfile)
        self.binding=(Config,original_get,original_from,checked_get,checked_fromfile)
        self.event('CONFIG_DEPENDENCY_ADAPTER_INSTALLED',scope='Exact frozen entry and literal inheritance edges; original Config.fromfile body retained',root=str(root))
    def restore(self):
        if self.binding:
            Config,get,frm,current_get,current_from=self.binding
            if Config._get_cfg_path is not current_get or Config.fromfile is not current_from:raise RuntimeError('CONFIG_DEPENDENCY_BINDING_DRIFT')
            Config._get_cfg_path=get;Config.fromfile=frm;self.binding=None
