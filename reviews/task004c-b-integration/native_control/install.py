"""Thin native method wrappers. All BA algebra and CUDA calls stay upstream."""
import functools
import inspect

from control_common import ControlError
from native_control.runtime import active


def selected_flags(original,phase,stage,video,motion_only,update_u,use_u):
    ctrl=active()
    if not ctrl.enabled:return original(phase,stage,video,motion_only,update_u,use_u)
    if phase is not None and (phase!=stage or phase not in ('frontend_local_predecision','frontend_local_retained') or motion_only):
        raise ControlError('Native intervention escaped the frozen local-BA scope')
    if not video.uncertainty_aware or not video.enable_affine_transform or video.enable_bidirectional_uncer:
        raise ControlError('Native W/U baseline contract changed')
    # The native initialization template intentionally has UBA=False during
    # its first 8 updates. W=1 means retain this template, not rewrite it.
    return ctrl.depth_flag(stage,bool(video.metric_depth_reg)),use_u,update_u


def _wrap(cls,name,adapter):
    original=getattr(cls,name)
    if getattr(original,'_gamecam_native_control',False):raise ControlError('Native hook installed twice: '+name)
    signature=inspect.signature(original)
    @functools.wraps(original)
    def wrapped(self,*args,**kwargs):
        ctrl=active()
        if not ctrl.enabled:return original(self,*args,**kwargs)
        bound=signature.bind(self,*args,**kwargs);bound.apply_defaults()
        return adapter(ctrl,self,bound,original)
    wrapped._gamecam_native_control=True
    setattr(cls,name,wrapped)


def _call(original,bound):return original(*bound.args,**bound.kwargs)


def install_factor_graph(cls):
    def constructor(c,g,b,f):
        result=_call(f,b);c.graph_created(g);return result
    _wrap(cls,'__init__',constructor)

    def add(c,g,b,f):
        p=c.begin('graph.add',{'graph_id':c.gid(g),'ii':_ints(b.arguments['ii']),'jj':_ints(b.arguments['jj']),'remove':bool(b.arguments['remove'])})
        if p['graph_id']!=c.gid(g) or len(p['ii'])!=len(p['jj']):raise ControlError('Invalid scheduled edge request')
        if any(type(x) is not int or not 0<=x<len(c.nodes) for x in p['ii']+p['jj']):raise ControlError('Impossible recorded graph endpoint')
        b.arguments.update(ii=p['ii'],jj=p['jj'],remove=p['remove'])
        result=_call(f,b);c.end('graph.add',{'graph_id':c.gid(g)});return result
    _wrap(cls,'add_factors',add)

    def remove(c,g,b,f):
        import torch
        mask=b.arguments['mask'];p=c.begin('graph.remove',{'graph_id':c.gid(g),'mask':mask.detach().cpu().tolist(),'store':bool(b.arguments['store'])})
        if p['graph_id']!=c.gid(g) or len(p['mask'])!=len(g.ii) or any(type(x) is not bool for x in p['mask']) or type(p['store']) is not bool:
            raise ControlError('Impossible recorded factor-removal event')
        b.arguments['mask']=torch.as_tensor(p['mask'],device=mask.device,dtype=torch.bool);b.arguments['store']=p['store']
        result=_call(f,b);c.end('graph.remove',{'graph_id':c.gid(g)});return result
    _wrap(cls,'rm_factors',remove)

    def remove_kf(c,g,b,f):
        ix=int(b.arguments['ix'])
        # The audited Frontend only removes its newest candidate. Do not
        # silently generalize this protocol to arbitrary buffer compaction.
        if ix!=len(c.nodes)-1:raise ControlError('Unaudited non-tail native keyframe removal')
        token=c.nodes[ix]
        c.begin('keyframe.remove',{'graph_id':c.gid(g),'slot':ix,'rgb_token':token},select=False)
        result=_call(f,b);c.nodes.pop();c.end('keyframe.remove',{'removed':token});return result
    _wrap(cls,'rm_keyframe',remove_kf)

    def mutation(kind):
        def adapter(c,g,b,f):
            c.begin(kind,{'graph_id':c.gid(g)},select=False)
            result=_call(f,b);c.end(kind,{'graph_id':c.gid(g)});return result
        return adapter
    _wrap(cls,'filter_edges',mutation('graph.filter'))
    _wrap(cls,'clear_edges',mutation('graph.clear'))

    def update(c,g,b,f):
        from task003_observer import recorder
        phase=recorder().stage;c.phase=phase
        controls={k:b.arguments[k] for k in ('t0','t1','itrs','use_inactive','EP','motion_only','enable_update_uncer','enable_udba','visualization_stage')}
        p=c.begin('graph.update',{'graph_id':c.gid(g),'phase':phase,'controls':controls})
        if p['graph_id']!=c.gid(g) or p['phase']!=phase:raise ControlError('BA stage mismatch')
        if set(p['controls'])!=set(controls):raise ControlError('BA graph controls mismatch')
        b.arguments.update(p['controls'])
        result=_call(f,b)
        if phase in ('frontend_init_neighborhood','frontend_init_proximity','frontend_init_second'):
            c.init_counts[phase]=c.init_counts.get(phase,0)+1
        c.end('graph.update',{'graph_id':c.gid(g),'phase':phase});return result
    _wrap(cls,'update',update)

    def lowmem(c,g,b,f):
        fields=('t0','t1','itrs','steps','use_inactive','EP','enable_wq','enable_update_uncer','enable_udba','visualization_stage','save_edges_weights')
        p=c.begin('graph.update_lowmem',{'graph_id':c.gid(g),'controls':{k:b.arguments[k] for k in fields}})
        if p['graph_id']!=c.gid(g) or set(p['controls'])!=set(fields):raise ControlError('Lowmem BA controls mismatch')
        b.arguments.update(p['controls']);result=_call(f,b)
        c.end('graph.update_lowmem',{'graph_id':c.gid(g)});return result
    _wrap(cls,'update_lowmem',lowmem)


def _ints(x):return [int(v) for v in (x.detach().cpu().tolist() if hasattr(x,'detach') else x)]


def install_depth_video(cls):
    def append(c,v,b,f):
        item=b.arguments['item'];rgb=int(item[0])+1;slot=int(v.counter.value)
        if slot!=len(c.nodes) or not 1<=rgb<=80:raise ControlError('Native insertion buffer/RGB mismatch')
        c.begin('keyframe.insert',{'rgb_id':rgb,'slot':slot,'token':'kf:%03d'%rgb},select=False)
        result=_call(f,b);c.nodes.append('kf:%03d'%rgb)
        c.end('keyframe.insert',{'counter_after':int(v.counter.value)});return result
    _wrap(cls,'append',append)

    def ba(c,v,b,f):
        c.ba_calls+=1
        from task003_observer import recorder
        phase=recorder().stage
        fields=('t0','t1','iters','lm','ep','gamma','tao','lr','weight_decay','motion_only','enable_update_uncer','enable_udba','visualization_stage','task004_phase')
        payload={'call':c.ba_calls,'phase':phase,'ii':_ints(b.arguments['ii']),'jj':_ints(b.arguments['jj']),
                 'controls':{k:b.arguments[k] for k in fields}}
        p=c.begin('native.ba',payload)
        if p['call']!=c.ba_calls or p['phase']!=phase or p['ii']!=payload['ii'] or p['jj']!=payload['jj'] or set(p['controls'])!=set(fields):
            raise ControlError('Native BA call ordering/edge set mismatch')
        b.arguments.update(p['controls'])
        _numeric(c,v,'before',b.arguments)
        result=_call(f,b)
        _numeric(c,v,'after',b.arguments)
        c.end('native.ba',{'call':c.ba_calls,'phase':phase});return result
    _wrap(cls,'ba',ba)


def _numeric(c,v,when,args):
    from checkpoint.checkpoint_adapter import value_sha
    n=int(v.counter.value)
    fields={k:value_sha(getattr(v,k)[:n]) for k in ('poses','disps','uncertainties')}
    fields.update({k:value_sha(args[k]) for k in ('target','weight','eta')})
    c.diagnostic('ba.continuous.'+when,call=c.ba_calls,phase=c.phase,tensor_sha256=fields)


def install_backend(cls):
    def dense(c,obj,b,f):
        p=c.begin('backend.dense',{'steps':b.arguments['steps'],'keyframes':list(c.nodes),
                 'enable_update_uncer':b.arguments['enable_update_uncer'],'enable_udba':b.arguments['enable_udba']})
        for k in ('steps','enable_update_uncer','enable_udba'):b.arguments[k]=p[k]
        result=_call(f,b);c.end('backend.dense',{'keyframes':list(c.nodes)});return result
    _wrap(cls,'dense_ba',dense)


def install_frontend(cls):
    def second(c,frontend,b,f):
        c.begin('init.second_stage',{'warmup':frontend.warmup},select=False)
        result=_call(f,b)
        c.end('init.second_stage',{'warmup':frontend.warmup})
        c.initialization_done(frontend);return result
    _wrap(cls,'initialize_second_stage',second)
