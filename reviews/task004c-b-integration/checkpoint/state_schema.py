"""Source-derived inventory checks. Does not claim live object closure."""
import torch
from control_common import ControlError
VIDEO=('timestamp images dirty npc_dirty poses disps zeros disps_up intrinsics mono_disps mono_disps_up depth_scale depth_shift valid_depth_mask valid_depth_mask_small fmaps nets inps dino_feats dino_feats_resize uncertainties affine_weights temp_y_cdot').split()
GRAPH=('coords0 ii jj age net inp damping target weight ii_inac jj_inac ii_bad jj_bad target_inac weight_inac').split()
MOTION=('net inp fmap MEAN STDV').split()
FRONTEND=('last_pose last_disp last_time').split()
def validate_runtime_state(s):
    required={'video','graph','motion_filter','frontend','cursor','rng','runtime','model_buffers','model_modes','observer'}
    if set(s)!=required:raise ControlError('Incomplete runtime sections')
    for section,fields in [('video',VIDEO),('graph',GRAPH+['corr_pyramid']),('motion_filter',MOTION),('frontend',FRONTEND)]:
        if set(fields)-set(s[section]):raise ControlError('Missing explicit state in '+section)
    cap=s['runtime']['capacity'];n=s['runtime']['counter']
    if not (0<n<=cap) or s['cursor']['next_input_index']!=s['cursor']['last_input_index']+1:raise ControlError('Invalid counter/cursor')
    if s['runtime']['first_mainloop_seen'] or not s['runtime']['second_initialization_complete'] or s['runtime']['init_D']!=0:raise ControlError('Not a common initialization boundary')
    for name in VIDEO:
        t=s['video'][name]
        if not isinstance(t,torch.Tensor) or (name!='affine_weights' and t.shape[0]!=cap):raise ControlError('Full video storage required: '+name)
    for suffix in ('','_inac','_bad'):
        a,b=s['graph']['ii'+suffix],s['graph']['jj'+suffix]
        if a.dtype!=torch.int64 or b.dtype!=torch.int64 or a.ndim!=1 or a.shape!=b.shape or any(bool(((t<0)|(t>=n)).any()) for t in (a,b)):
            raise ControlError('Invalid graph reference: '+suffix)
    if s['graph']['age'].shape!=s['graph']['ii'].shape:raise ControlError('Graph age mismatch')
    if len(s['runtime']['keyframe_ids'])!=n or len(set(s['runtime']['keyframe_ids']))!=n:raise ControlError('Invalid keyframe identities')
    if len(s['graph']['corr_pyramid'])!=4:raise ControlError('All four correlation pyramid levels required')
    return {'valid':True,'native_object_closure_verified':False}
class ExplicitBindings:
    """Register every mutable attribute; unknown/missing attributes stop capture."""
    def __init__(self,owner,fields,excluded=()):self.owner=owner;self.fields=tuple(fields);self.excluded=set(excluded)
    def capture(self):
        unknown=set(vars(self.owner))-set(self.fields)-self.excluded;missing=set(self.fields)-set(vars(self.owner))
        if unknown or missing:raise ControlError('Binding inventory mismatch: unknown=%s missing=%s'%(sorted(unknown),sorted(missing)))
        return {name:getattr(self.owner,name) for name in self.fields}
    def restore_cpu_in_place(self,state):
        current=self.capture()
        if set(current)!=set(state):raise ControlError('Binding field mismatch')
        for k,dst in current.items():
            src=state[k]
            if isinstance(dst,torch.Tensor):
                if not isinstance(src,torch.Tensor) or dst.device.type!='cpu' or src.device.type!='cpu' or dst.dtype!=src.dtype or dst.shape!=src.shape or dst.stride()!=src.stride():raise ControlError('CPU binding tensor mismatch: '+k)
            elif type(src)!=type(dst):raise ControlError('Binding scalar type mismatch: '+k)
        with torch.no_grad():
            for k,dst in current.items():
                if isinstance(dst,torch.Tensor):dst.copy_(state[k])
                else:setattr(self.owner,k,state[k])
