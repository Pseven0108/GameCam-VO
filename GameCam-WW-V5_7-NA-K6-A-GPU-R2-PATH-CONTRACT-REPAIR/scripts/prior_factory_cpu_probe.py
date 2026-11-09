"""Real frozen factory calls; no mocks, checkpoint deserialization, or forward."""
import gc,importlib,inspect,json,os,pathlib,resource,sys,time,traceback

def run_factories(c,torch,guard):
    torch.set_num_threads(4)
    rows=[];calls=[];start=time.monotonic()
    def profile(frame,event,arg):
        guard.profile(frame,event,arg)
        if event=='call':
            f=frame.f_code.co_filename;n=frame.f_code.co_name
            if n in ('metric3d_vit_large','get_configured_monodepth_model','get_monodepth_model','vit_large_reg','dinov2_reg_small_fine','load_model','create_model','vit_small_patch14_reg4_dinov2'):
                calls.append(dict(function=n,file=f,pretrained=frame.f_locals.get('pretrained'),pretrain=frame.f_locals.get('pretrain'),checkpoint=frame.f_locals.get('checkpoint'),monotonic_time=time.monotonic()))
    def memory():
        values={}
        for line in pathlib.Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('VmRSS:','VmHWM:')):values[line.split(':')[0]+'_MiB']=int(line.split()[1])/1024
        values['process_peak_RSS_MiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        return values
    def measured(name,fn):
        before=time.monotonic();mem=memory()
        try:v=fn()
        except BaseException:
            rows.append(dict(stage=name,status='ERROR',seconds=time.monotonic()-before,memory_before=mem,memory_after=memory(),traceback=traceback.format_exc()));raise
        rows.append(dict(stage=name,status='PASS',seconds=time.monotonic()-before,memory_before=mem,memory_after=memory()));return v
    def hub(e):
        with torch.hub._add_to_sys_path(str(pathlib.Path(e['requested_path']).parent)):
            return torch.hub._import_module(torch.hub.MODULE_HUBCONF,e['requested_path'])
    def describe(model):
        assert isinstance(model,torch.nn.Module)
        parameters=list(model.parameters());buffers=list(model.buffers());bad=[type(p).__name__ for p in parameters if isinstance(p,torch.nn.parameter.UninitializedParameter)]
        assert not bad and all(p.device.type=='cpu' for p in parameters+buffers)
        return dict(type=type(model).__module__+'.'+type(model).__name__,real_nn_Module=True,parameters=sum(p.numel() for p in parameters),trainable_parameters=sum(p.numel() for p in parameters if p.requires_grad),buffers=sum(p.numel() for p in buffers),parameter_bytes=sum(p.numel()*p.element_size() for p in parameters),device_types=sorted({p.device.type for p in parameters+buffers}),uninitialized_parameters=bad,children=[dict(name=n,type=type(m).__module__+'.'+type(m).__name__) for n,m in model.named_children()],submodule_count=sum(1 for _ in model.modules()),real_weights_loaded=False,forward_executed=False)
    oldprofile=sys.getprofile();sys.setprofile(profile)
    try:
        entries=c['dynamic_source_policy']['hub_entrypoints'];m=measured('metric3d_hub_import',lambda:hub(entries[0]));Config=m.Config;entry=str(pathlib.Path(entries[0]['real_path']).parent/c['prior_factory_policy']['metric3d_entry_config'])
        cg=Config.__dict__['_get_cfg_path'];cf=Config.fromfile;original_get=Config._get_cfg_path.__wrapped__;original_from=cf.__wrapped__
        before=time.monotonic()
        try:
            Config._get_cfg_path=staticmethod(original_get)
            original_from(entry)
            raise AssertionError('EXPECTED_FROZEN_CONFIG_PATH_FAILURE_NOT_OBSERVED')
        except (FileNotFoundError,RuntimeError) as e:
            missing=str(pathlib.Path(entries[0]['real_path']).parent/'mono/configs/_base_/datasets/_data_base_.py')
            assert isinstance(e,FileNotFoundError) or str(e)=='MODEL_UNAPPROVED_PROJECT_READ:'+missing,str(e)
            negative=dict(status='EXPECTED_FAILURE_REPRODUCED',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-before)
        finally:Config._get_cfg_path=cg
        cfg=measured('Metric3D.Config.fromfile.corrected_exact_dependency',lambda:Config.fromfile(entry))
        config_report=dict(status='PASS_WITH_EXACT_PATH_REPAIR',Config_class=Config.__module__+'.'+Config.__qualname__,entry=entry,original_path_control=negative,model_config=cfg.model.to_dict(),data_basic=cfg.data_basic.to_dict(),raw_config_files_modified=False,original_Config_fromfile_body_executed=True,dependency_events='model/config_dependency_events.jsonl')
        signature=str(inspect.signature(m.metric3d_vit_large));model=measured('Metric3D.metric3d_vit_large(pretrain=False)',lambda:m.metric3d_vit_large(pretrain=False))
        metric=dict(status='PASS',factory='metric3d_vit_large',signature=signature,kwargs={'pretrain':False},model=describe(model),nested_real_factory_calls=[x for x in calls if x['function'] in ('get_configured_monodepth_model','get_monodepth_model','vit_large_reg')])
        assert any(x['function']=='get_configured_monodepth_model' for x in calls)
        del model;gc.collect()
        f=measured('fit3d_hub_import',lambda:hub(entries[1]));timm=importlib.import_module('timm');factory=c['prior_factory_policy']['timm_factory'];from timm.models import model_entrypoint
        ep=model_entrypoint(factory['model_name'].split('.')[0]);registry=dict(status='PASS',timm_version=timm.__version__,model_name=factory['model_name'],registered=timm.is_model(factory['model_name'].split('.')[0]),entrypoint=ep.__module__+'.'+ep.__name__,entrypoint_signature=str(inspect.signature(ep)),source_file=inspect.getfile(ep),create_model_signature=str(inspect.signature(timm.create_model)))
        before=time.monotonic();count=len(guard.events)
        try:
            f.dinov2_reg_small_fine()
            raise AssertionError('FIT3D_NATIVE_NO_PRETRAINED_GUARD_MISSED')
        except RuntimeError as e:
            assert str(e)=='CPU_PREFLIGHT_PRETRAINED_TRUE_FORBIDDEN',str(e)
            fit=dict(status='UNVERIFIED_NO_SAFE_PRETRAINED_PATH',factory='dinov2_reg_small_fine',signature=str(inspect.signature(f.dinov2_reg_small_fine)),load_model_signature=str(inspect.signature(f.load_model)),real_native_entry_called=True,rejected_before_timm_body=True,reason='Frozen factory hardcodes pretrained=True, then unconditionally loads FiT3D checkpoint. No safe public false flag exists.',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-before,guard_events=guard.events[count:],model_returned=False)
        # CPython unsets a profiling callback when it raises. Re-arm after
        # the deliberately refused native pretrained request before safe construction.
        sys.setprofile(profile);assert sys.getprofile() is profile
        model=measured('timm.create_model(pretrained=False)',lambda:timm.create_model(factory['model_name'],**factory['kwargs']))
        dino=dict(status='PASS',factory='timm.create_model',model_name=factory['model_name'],kwargs=factory['kwargs'],model=describe(model),coverage='Exact underlying FiT3D DINOv2-small-reg4 architecture; does not validate FiT3D native pretrained wrapper or weights')
        assert sys.getprofile() is profile
        assert any(x['function']=='create_model' and x['pretrained'] is False for x in calls)
        dino['profile_guard_active_through_factory']=True
        assert 'VisionTransformer' in dino['model']['type'];del model;gc.collect()
        measured('metric3d_repeat_import',lambda:hub(entries[0]));measured('fit3d_repeat_import',lambda:hub(entries[1]));guard.pins.assert_hooks(require_torch=True)
        assert not torch.cuda.is_initialized()
        return dict(status='PRIOR_MODEL_FACTORY_CPU_PREFLIGHT_PARTIAL_PASS',config=config_report,metric3d=metric,fit3d=fit,timm_registry=registry,dinov2=dino,timing=rows,call_trace=calls,total_seconds=time.monotonic()-start,memory=memory(),torch_threads=torch.get_num_threads(),guard=guard.snapshot(),real_checkpoints_loaded=0,real_forward_executed=False)
    finally:sys.setprofile(oldprofile)
