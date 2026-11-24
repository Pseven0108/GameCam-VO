"""Single admitted capture. Adds diagnostics/completeness checks, never BA algebra."""
import os,json,pathlib,hashlib,sys

def install_capture_checks(root):
 import torch
 from native_control import binding
 from native_control.runtime import active
 from checkpoint.checkpoint_adapter import value_sha
 from native_control.snapshot import read_manifest
 from control_common import ControlError
 import src.depth_video as depth_module
 original_selector=depth_module.selected_flags
 def selected_audit(original,phase,stage,video,motion_only,update_u,use_u):
  flags=original_selector(original,phase,stage,video,motion_only,update_u,use_u)
  c=active()
  if c.enabled:
   depth=video.mono_disps if flags[0] else video.zeros
   c.diagnostic('ba.actual.selected_inputs',call=c.ba_calls,phase=phase,observer_stage=stage,
      D_actual=bool(flags[0]),enable_udba_actual=bool(flags[1]),enable_update_uncer_actual=bool(flags[2]),
      motion_only=bool(motion_only),depth_source='video.mono_disps' if flags[0] else 'video.zeros',
      input_depth_sha256=value_sha(depth),input_depth_shape=list(depth.shape),
      initialization_template_W_not_globally_overridden=True)
  return flags
 depth_module.selected_flags=selected_audit
 protocol=json.loads((root/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').read_text())
 original_inventory=binding.state_inventory
 def checked_inventory(bundle,**kwargs):
  tracker=bundle['tracker'];video=tracker.video
  if bundle['cursor']['next_input_index']!=18 or bundle['stream'].seen!=18:
   raise ControlError('C0 requested outside actual RGB018 frame-end boundary')
  if bundle['control']['ba_calls']!=24:raise ControlError('C0 native BA count differs from 24')
  families=[]
  for f in protocol['tensors']:
   name=f['name'];parts=name.replace('frontend.graph.corr.corr_pyramid[*]','frontend.graph.corr.corr_pyramid').split('.')
   if parts[0]=='video':value=video;parts=parts[1:]
   elif parts[0]=='motion_filter':value=tracker.motion_filter;parts=parts[1:]
   elif parts[0]=='frontend':value=tracker.frontend;parts=parts[1:]
   else:raise ControlError('Unknown required family '+name)
   for part in parts:
    if not hasattr(value,part):raise ControlError('Missing required state family '+name)
    value=getattr(value,part)
   values=value if isinstance(value,list) else [value]
   if 'corr_pyramid' in name and len(values)!=4:raise ControlError('Correlation pyramid must have four levels')
   rows=[]
   for v in values:
    if not isinstance(v,torch.Tensor):raise ControlError('Required state family is not Tensor '+name)
    if f.get('expected_shape') and list(v.shape)!=f['expected_shape']:raise ControlError('Required shape differs '+name)
    if f.get('expected_dtype') and str(v.dtype)!=f['expected_dtype']:raise ControlError('Required dtype differs '+name)
    rows.append({'shape':list(v.shape),'stride':list(v.stride()),'dtype':str(v.dtype),'offset':v.storage_offset(),'device':str(v.device),'logical_sha256':value_sha(v),'storage_bytes':v.untyped_storage().nbytes()})
   families.append({'name':name,'values':rows})
  if len(families)!=47:raise ControlError('Expected exactly 47 state families')
  buffers=[]
  models={'DroidNet':tracker.net,'Metric3D':tracker.motion_filter.metric_depth_estimator,'FiT3D':tracker.motion_filter.feat_extractor}
  for model_name,model in models.items():
   for name,v in model.named_buffers():buffers.append({'model':model_name,'buffer':name,'dtype':str(v.dtype),'shape':list(v.shape),'sha256':value_sha(v)})
  inventory=original_inventory(bundle,**kwargs)
  inventory['explicit_required_47_families']=families
  inventory['all_live_network_buffers']=buffers
  inventory['C0_boundary_verified']={'RGB_processed':18,'next_index':18,'next_RGB':19,'native_BA_calls':24,'INIT_D':0,'source_pid':os.getpid()}
  (root/'evidence/C0_LIVE_CLOSURE_INVENTORY.json').write_text(json.dumps(inventory,indent=2))
  return inventory
 binding.state_inventory=checked_inventory

if __name__=='__mp_main__' and os.environ.get('GAMECAM_NATIVE_APPROVED_MODE')=='capture':
 # Spawn starts a new interpreter; process-local audit hooks must be installed
 # there too. They are not numerical state and are never serialized into C0.
 install_capture_checks(pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE']))

if __name__=='__main__':
 import torch.multiprocessing as mp
 assert os.environ.get('GAMECAM_NATIVE_APPROVED_MODE')=='capture'
 mp.set_start_method('spawn',force=True)
 root=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])
 install_capture_checks(root)
 from runner.run_native_smoke import main
 sys.exit(main())
