"""CPU-only import closure under the same Python file boundary as the V2 child."""
import argparse,csv,json,os,pathlib,subprocess,sys,time
from runtime_dependency_pins import RuntimePins
from model_io_boundary_v2 import ModelIOBoundary


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase-root',required=True);p.add_argument('--evidence-root',required=True);a=p.parse_args()
    started=time.monotonic()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    phase=pathlib.Path(a.phase_root).resolve();root=phase.parent;ev=pathlib.Path(a.evidence_root);prod=pathlib.Path('/root/rivermind-data/gamecam/GameCam-VO')
    pins=RuntimePins(phase);case=json.loads(pins._frozen_files['cases.json'].decode('utf-8-sig'))[0]
    tracked=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root,capture_output=True,check=True).stdout
    sources=[str(root/os.fsdecode(s)) for s in tracked.split(b'\0') if s]
    inventory=list(csv.DictReader((ev/'inputs/remote_source_inventory.csv').open(encoding='utf-8-sig',newline='')))
    sources += [str(prod/r['relative_path']) for r in inventory if r['relative_path'].startswith('baselines/droid_w/prior_sources/') and r['hash_status']=='HASHED']
    reads=[str(phase/'config/dependency_pins.json'),str(ev/'data-validation/effective_config_120.json')]
    reads += [str(phase/r['path']) for r in pins.spec['files'].values()]
    for r in [pins.spec['config'],pins.spec['k4_live_contract']]+list(pins.weights.values()):reads += [r['path_linux'],r['real_linux']]
    reads += [pins.spec['hf']['ref_path_linux'],pins.spec['hf']['ref_real_linux']]+[r['path_linux'] for r in case['frames']]
    scratch=ev/'cpu-import-closure-output'/'tmp';scratch.mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(scratch)
    boundary=ModelIOBoundary(reads,sources,[root,prod],[ev/'cpu-import-closure-output'],[sys.prefix]);boundary.install()
    os.environ.update(pins.spec['environment']);pins.install_before_import()
    import torch,cv2,numpy
    assert not torch.cuda.is_initialized();pins.assert_hooks(require_torch=True)
    availability_calls=[]
    def cpu_unavailable():availability_calls.append(True);return False
    def forbidden_cuda_init(*args,**kwargs):raise AssertionError('CUDA_INITIALIZATION_FORBIDDEN_IN_CPU_SMOKE')
    torch.cuda.is_available=cpu_unavailable;torch.cuda.init=forbidden_cuda_init;torch.cuda._lazy_init=forbidden_cuda_init
    pre_guard_setup_seconds=time.monotonic()-started
    repo=root/'baselines/droid_w/upstream';os.chdir(repo);sys.path.insert(0,str(repo))
    from native_adapter_v2 import _native_runtime
    from native_linux_guard_v2 import Guard
    from src.depth_video import DepthVideo
    from src.modules.droid_net import DroidNet
    from src.tracker import Tracker
    from src.utils.datasets import get_dataset,RGB_NoPose
    cfg=json.loads((ev/'data-validation/effective_config_120.json').read_text())
    dataset=get_dataset(cfg,device='cpu');assert type(dataset) is RGB_NoPose and len(dataset)==120
    idx,img,depth,pose=dataset[0];assert idx==0 and pose is None and img.device.type=='cpu'
    assert not torch.cuda.is_initialized()
    report={'status':'PASS','scope':'Real native class imports and one CPU RGB sample under V2 ModelIOBoundary; no class/model construction or native Tracker.run','classes_imported':['Guard','DepthVideo','DroidNet','Tracker','RGB_NoPose'],'source_allowlist_files':len(sources),'denied_io_events':boundary.events,'dataset_frames':len(dataset),'sample_device':str(img.device),'sample_shape':list(img.shape),'cuda_initialized':False,'model_constructed':False,'checkpoint_load_events':[e for e in pins.events if e['event']=='weight_load_started'],'GT_values_read':False,'pycache_prefix':sys.pycache_prefix,'native_tracker_called':False,'pre_guard_CPU_setup_seconds':pre_guard_setup_seconds,'whole_CPU_import_scope_seconds':time.monotonic()-started,'availability_checks_mocked':len(availability_calls),'cuda_initialization_entrypoints_forbidden':True}
    # Only this test's dedicated output is writable under the installed boundary.
    dest=ev/'cpu-import-closure-output';dest.mkdir(exist_ok=True);(dest/'native_import_closure.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));pins.gate.close()
if __name__=='__main__':main()
