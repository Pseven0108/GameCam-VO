"""CPU import probes: real sources, no selected model entrypoint calls."""
import importlib,json,os,pathlib,sys,time

def import_prior_sources(candidate, torch):
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
    rows=[];start=time.monotonic()
    def measured(label,fn):
        before=time.monotonic();v=fn();rows.append(dict(label=label,seconds=time.monotonic()-before,module=getattr(v,'__name__',None),path=getattr(v,'__file__',None),loader=type(getattr(v,'__loader__',None)).__name__));return v
    entries=candidate['dynamic_source_policy']['hub_entrypoints']
    metric=pathlib.Path(entries[0]['real_path']).parent
    def actual_local_hub_source(entry):
        with torch.hub._add_to_sys_path(str(pathlib.Path(entry['requested_path']).parent)):
            return torch.hub._import_module(torch.hub.MODULE_HUBCONF,entry['requested_path'])
    m=measured('Metric3D.hubconf',lambda:actual_local_hub_source(entries[0]))
    assert callable(m.metric3d_vit_large)
    selected=[
        'mono.model.monodepth_model','mono.model.model_pipelines.__base_model__',
        'mono.model.model_pipelines.dense_pipeline','mono.model.backbones.ViT_DINO_reg',
        'mono.model.decode_heads.RAFTDepthNormalDPTDecoder5',
    ]
    for name in selected:measured(name,lambda n=name:importlib.import_module(n))
    f=measured('FiT3D.hubconf',lambda:actual_local_hub_source(entries[1]))
    assert callable(f.dinov2_reg_small_fine)
    measured('timm.models.vision_transformer',lambda:importlib.import_module('timm.models.vision_transformer'))
    # Verify the selected timm entrypoint registration without calling a factory.
    from timm.models import model_entrypoint
    dino_entry=model_entrypoint('vit_small_patch14_reg4_dinov2')
    rows.append(dict(label='selected_timm_DINO_entrypoint',module=dino_entry.__module__,function=dino_entry.__name__,factory_called=False,seconds=0))
    upstream=pathlib.Path(candidate['source_root'])/'baselines/droid_w/upstream';sys.path.insert(0,str(upstream))
    for name in ['src.utils.mono_priors.metric_depth_estimators','src.utils.mono_priors.img_feature_extractors']:
        measured(name,lambda n=name:importlib.import_module(n))
    again=measured('Metric3D.hubconf.repeat',lambda:actual_local_hub_source(entries[0]))
    assert again is not m and torch.hub.MODULE_HUBCONF not in sys.modules
    again=measured('FiT3D.hubconf.repeat',lambda:actual_local_hub_source(entries[1]))
    assert again is not f and torch.hub.MODULE_HUBCONF not in sys.modules
    assert not torch.cuda.is_initialized()
    return dict(status='REAL_PRIOR_IMPORTS_PASSED',rows=rows,total_dynamic_seconds=time.monotonic()-start,model_entrypoints_called=0,CUDA_initialized=False,real_checkpoints_loaded=0,unused_branches_tested=False)
