"""Tracker state boundary, explicit I/O rebinding, and restore receipts."""
import json
import os
from pathlib import Path

import torch
from control_common import ControlError, file_sha, require_space, digest
from checkpoint.rng_state import capture_rng_state, restore_rng_state
from native_control.snapshot import save_state,load_state,state_inventory,ObjectEncoder,prepare_state,save_prepared_state

CURSOR_FIELDS={'next_input_index','prev_kf_idx','curr_kf_idx','prev_ba_idx','intrinsic'}


def services_for(tracker,stream,barrier,observer=None):
    # These are external I/O/coordination objects, not numerical optimization state.
    # Their relevant counter values are separately captured and checked.
    return {'tracker_pipe':tracker.pipe,'event_writer':tracker.event_writer,'printer':tracker.printer,
            'video_counter':tracker.video.counter,'writer_barrier':barrier,
            'observer_file':observer._file if observer is not None else None}


def input_identity(stream,index):
    if not 0<=index<80:raise ControlError('C0 next frame must be within the authorized prefix')
    path=Path(stream.color_paths[index])
    return {'input_index':index,'rgb_id':index+1,'path':str(path),'sha256':file_sha(path),
            'manifest_sha256':stream.manifest_sha256,'intrinsic':stream.get_intrinsic().tolist()}


def live_bundle(tracker,stream,values,controller,filler,barrier):
    from task003_observer import recorder
    from src.utils.sys_timer import timer
    if set(values)!=CURSOR_FIELDS:raise ControlError('Tracker cursor closure fields incomplete')
    if not controller.initialized or controller.init_counts!={'frontend_init_neighborhood':8,'frontend_init_proximity':8,'frontend_init_second':8}:
        raise ControlError('C0 is not after all 24 initialization graph updates')
    if values['next_input_index']!=controller.rgb or values['next_input_index']>79:
        raise ControlError('C0 boundary/next input mismatch')
    if values['next_input_index']!=18:
        raise ControlError('Actual initialization boundary differs from the RGB018 candidate; preserve trace for protocol review')
    if tracker.cfg['tracking']['buffer']!=500 or tracker.cfg['mapping']['enable'] or tracker.enable_online_ba:
        raise ControlError('Snapshot runtime differs from audited no-mapping R2 scope')
    return {'tracker':tracker,'stream':stream,'filler':filler,'cursor':values,'control':controller.snapshot_discrete(),
            'counter_value':int(tracker.video.counter.value),'next_input':input_identity(stream,values['next_input_index']),
            'printer_progress':int(tracker.printer.progress_counter.value),
            'observer':recorder(),'timer':timer,'rng':capture_rng_state(),'process_environment':{'PYTHONHASHSEED':os.environ.get('PYTHONHASHSEED'),
             'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda}}


def capture_c0(path,tracker,stream,values,controller,filler,barrier,identity_lock):
    if not torch.cuda.is_initialized():raise ControlError('Native C0 needs the actual admitted CUDA tracker process')
    if barrier is None:raise ControlError('Rerun writer barrier missing')
    with barrier.quiesce(),tracker.video.get_lock():
        torch.cuda.synchronize()
        bundle=live_bundle(tracker,stream,values,controller,filler,barrier)
        services=services_for(tracker,stream,barrier,bundle['observer'])
        inventory=state_inventory(bundle,services=services)
        # One C0 plus journal/observer headroom. No archive or second C0 is created.
        require_space(Path(path).parent,inventory['storage_bytes']+512*1024**2,10*1024**3)
        provenance={'artifact_kind':'NATIVE_C0','writer_barrier_and_closure_passed':True,
                    'baseline_commit':identity_lock['baseline_commit'],'identity_lock_sha256':digest(identity_lock),
                    'initialization_D':0,'W':1,'U':1,'source_pid':os.getpid(),'actual_boundary_rgb':controller.rgb,
                    'next_input':bundle['next_input'],'inventory':inventory}
        prepared=prepare_state(bundle,provenance=provenance,services=services,destination_parent=Path(path).parent)
        budget_file=Path(path).parent/'C0_EXACT_BUDGET_BEFORE_SAVE.json'
        with budget_file.open('x') as f:json.dump(prepared['budget'],f,indent=2)
        return save_prepared_state(prepared,path)


def restore_c0(path,*,services,expected_sha,allow_cuda=False):
    factory=None
    arena_root=os.environ.get('GAMECAM_FILE_BACKED_CPU_ROOT')
    if arena_root:
        from native_control.file_backed import FileArena
        arena=FileArena(Path(arena_root));factory=arena.restore_storage
    bundle,manifest=load_state(path,services=services,expected_sha=expected_sha,allow_cuda=allow_cuda,cpu_storage_factory=factory)
    if manifest['provenance']['artifact_kind']!='NATIVE_C0':raise ControlError('A synthetic state cannot restore a real C0')
    if bundle['process_environment']!={'PYTHONHASHSEED':os.environ.get('PYTHONHASHSEED'),
            'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda}:
        raise ControlError('Restore interpreter/RNG environment differs from capture')
    tracker,stream=bundle['tracker'],bundle['stream']
    tracker.video.counter.value=bundle['counter_value']
    tracker.printer.progress_counter.value=bundle['printer_progress']
    if input_identity(stream,bundle['cursor']['next_input_index'])!=bundle['next_input']:
        raise ControlError('Restored next RGB input/K identity differs')
    if tracker.motion_filter.video is not tracker.video or tracker.frontend.graph.video is not tracker.video or bundle['filler'].video is not tracker.video:
        raise ControlError('Restored native object references do not close')
    # Complete graph and tensor metadata are compared before changing I/O paths.
    enc=ObjectEncoder(services=services);tree=enc.encode(bundle)
    restored={k:v for k,v in enc.nodes.items()}
    if tree!=manifest['root'] or restored!=manifest['nodes']:
        raise ControlError('Native restore object/tensor/alias/attribute manifest mismatch')
    restore_rng_state(bundle['rng'])  # Last operation that may affect RNG.
    return bundle,manifest,{'all_tensor_and_object_nodes_match':True,'next_input_match':True,
          'object_nodes':len(restored),'new_process_pid':os.getpid(),'source_pid':manifest['provenance'].get('source_pid'),
          'rng_restored_last':True,'c0_sha256':manifest['state_sha256']}


def rebind_output(bundle,out):
    """Only output destinations change; check before/after identity explicitly."""
    out=Path(out);tracker=bundle['tracker'];cfg=tracker.cfg
    cfg['data']['output']=str(out)
    tracker.output=str(out/cfg['scene']);tracker.video.output=tracker.output
    tracker.motion_filter.save_dir=tracker.output
    tracker.online_ba.output=tracker.output;tracker.frontend.loop_closing.output=tracker.output
    bundle['stream'].out=out
    return {'rebased_fields':['cfg.data.output','tracker.output','video.output','motion_filter.save_dir',
             'online_ba.output','frontend.loop_closing.output','stream.out'],'algorithm_config_changed':False}
