"""Use the real upstream RGB_NoPose on CPU and a fake tracker, never Tracker.run."""
import argparse,hashlib,json,os,pathlib,sys,time
from runtime_dependency_pins import RuntimePins,require
from model_io_boundary_v2 import ModelIOBoundary

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase-root',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args();assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    phase=pathlib.Path(a.phase_root).resolve();repo=phase.parent/'baselines/droid_w/upstream';pins=RuntimePins(phase);case=json.loads(pins._frozen_files['cases.json'].decode('utf-8-sig'))[0]
    cfg=json.loads(pathlib.Path(a.config).read_text());assert cfg['dataset']=='youtube' and cfg['max_frames']==120 and cfg['stride']==1
    os.environ.update(pins.spec['environment']);pins.install_before_import()
    import torch,cv2,numpy as np
    assert not torch.cuda.is_initialized();pins.assert_hooks(require_torch=True);torch.set_num_threads(2);cv2.setNumThreads(2)
    sys.path.insert(0,str(repo))
    from src.utils.datasets import get_dataset,RGB_NoPose
    # All dependency imports above are source imports; no real model or checkpoint is constructed.
    dataset=get_dataset(cfg,device='cpu');assert type(dataset) is RGB_NoPose and len(dataset)==120 and dataset.poses is None and dataset.depth_paths is None
    assert [str(pathlib.Path(p).resolve()) for p in dataset.color_paths]==[str(pathlib.Path(f['path_linux']).resolve()) for f in case['frames']]
    rows=[]
    class FakeTracker:
        def run(self,stream):
            for i in range(len(stream)):
                idx,img,depth,pose=stream[i];assert idx==i and pose is None
                assert depth.device.type=='cpu' and tuple(depth.shape)==(288,512) and int(torch.count_nonzero(depth))==0
                assert img.device.type=='cpu' and tuple(img.shape)==(1,3,288,512) and bool(torch.isfinite(img).all())
                bgr=(img[0].permute(1,2,0).numpy()*255).round().astype(np.uint8)[:,:,::-1].copy();actual=hashlib.sha256(bgr.tobytes()).hexdigest();assert actual==case['frames'][i]['decoded_bgr_sha256']
                rows.append({'ordinal':i,'published_frame':7953+i,'tensor_device':'cpu','rgb_shape':list(img.shape),'pose_is_none':True,'depth_is_zero_placeholder':True,'GT_depth_supplied':False,'decoded_bgr_sha256':actual,'passed':True})
    start=time.monotonic();FakeTracker().run(dataset);assert not torch.cuda.is_initialized()
    out=pathlib.Path(a.output);out.write_text(json.dumps({'status':'PASS','real_dataset_class':'src.utils.datasets.RGB_NoPose','native_tracking_called':False,'fake_tracker_frames':len(rows),'torch_version':str(torch.__version__),'tensor_device':'cpu','native_depth_contract':'zero placeholder tensor synthesized by BaseDataset when depth_paths=None; native Tracker ignores sample fields 3 and 4','cuda_initialized':False,'checkpoint_load_events':[e for e in pins.events if e['event']=='weight_load_started'],'GT_values_read':False,'pose_values_generated':0,'seconds':time.monotonic()-start,'frames':rows},indent=2)+'\n');print(json.dumps({'status':'PASS','real_dataset_class':'RGB_NoPose','frames':len(rows),'cuda_initialized':False,'GT_values_read':False}))
    pins.gate.close()
if __name__=='__main__':main()
