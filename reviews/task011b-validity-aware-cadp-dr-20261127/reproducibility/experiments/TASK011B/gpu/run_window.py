"""Native SLAM.spawn tracking, final BA and filler with task-local prior hook."""
import argparse,json,time,traceback,importlib.util,faulthandler
faulthandler.enable(all_threads=True)
import numpy as np
from runtime import *
import torch
from src.slam import SLAM
from src.frontend import Frontend
from src.utils.common import setup_seed
import src.motion_filter as motion
from controller import arm_config,coefficient_map,install,MAIN


class ObservedSLAM(SLAM):
    def terminate(self):
        if not self.tracker.frontend.is_initialized:
            n=int(self.video.counter.value)
            np.savez_compressed(self.task_out/'initialization_partial.npz',timestamps=self.video.timestamp[:n].cpu().numpy(),poses_w2c=self.video.poses[:n].cpu().numpy())
            write(self.task_out/'ALGORITHM_FAILURE.json',dict(status='TRACKING_INITIALIZATION_FAILED',input_frames=64,keyframes=n))
            raise RuntimeError('TRACKING_NEVER_INITIALIZED: preserve native parameters and partial state')
        return super().terminate()

    def tracking(self,pipe):
        try:return self._tracking_impl(pipe)
        except BaseException as e:
            write(self.task_out/'CHILD_EXCEPTION.json',dict(type=type(e).__name__,error=str(e),traceback=traceback.format_exc()))
            if self.task_arm=='A6' and any(s in str(e) for s in ['TASK011B prior-free','TASK011B nonfinite/negative geometry','TASK011B empty positive-disparity']):
                n=int(self.video.counter.value)
                np.savez_compressed(self.task_out/'geometry_failure_partial.npz',timestamps=self.video.timestamp[:n].cpu().numpy(),
                    poses_w2c=self.video.poses[:n].cpu().numpy(),disps=self.video.disps[:n].cpu().numpy(),U=self.video.uncertainties[:n].cpu().numpy())
                write(self.task_out/'ALGORITHM_FAILURE.json',dict(status='CADP_GEOMETRY_DOMAIN_FAILURE',keyframes=n,error=str(e)))
            raise

    def _tracking_impl(self,pipe):
        write(self.task_out/'CHILD_ENTERED.json',dict(status='ENTERED_AFTER_SPAWN'))
        offline_hub()
        out=self.task_out;window=self.task_window;arm=self.task_arm
        cache=TASK/'cache'/window;meta=json.loads((cache/'CACHE_RECEIPT.json').read_text())
        if meta['status']!='COMPLETE' or meta['frames']!=64 or not meta['native_forward_RNG_unchanged']:
            raise RuntimeError('Common cache not admitted')
        if meta.get('precision_protocol')!='NATIVE_MOTION_FILTER_AUTOCAST_V2' or not meta.get('autocast_enabled') or meta.get('autocast_dtype')!='torch.float16' or meta.get('input_preprocess_device')!='cpu':
            raise RuntimeError('Prior cache does not preserve native MotionFilter precision')
        coefficients={}
        write(out/'CHILD_STAGE.json',dict(stage='LOAD_COMMON_PRIORS'))
        for r in meta['records']:
            path=cache/f'{r["timestamp"]:05d}.npz'
            if sha(path)!=r['sha256']:raise RuntimeError('Cached prior hash mismatch')
            with np.load(path,allow_pickle=False) as z:
                s,counts=coefficient_map(z['native_depth'],z['flip_depth'][:,::-1],z['native_confidence'],z['tta_valid'],arm_config(arm))
                coefficients[r['timestamp']]=s
        original_predictor=motion.predict_metric_depth
        def cached_depth(model,timestamp,image,cfg,device,**kwargs):
            with np.load(cache/f'{int(timestamp):05d}.npz',allow_pickle=False) as z:
                value=torch.from_numpy(z['native_depth'].copy()).to(device)
            if arm=='A0' and int(timestamp)==0:
                if not torch.is_autocast_enabled() or torch.get_autocast_gpu_dtype()!=torch.float16:
                    raise RuntimeError('Actual native tracking autocast context changed')
                before_cpu=torch.get_rng_state().clone();before_cuda=torch.cuda.get_rng_state().clone()
                t=time.perf_counter();reference=original_predictor(model,timestamp,image,cfg,device,save_depth=False)
                torch.cuda.synchronize()
                passed=torch.equal(reference,value)
                proof=dict(status='PASS' if passed else 'FAILED',timestamp=0,rgb_id=inputs(window)['frames'][0]['rgb_id'],
                    bitwise_equal=passed,max_absolute_error=float((reference-value).abs().max().item()),
                    actual_dtype=str(reference.dtype),cache_dtype=str(value.dtype),native_autocast_enabled=True,
                    cpu_RNG_unchanged=torch.equal(before_cpu,torch.get_rng_state()),
                    cuda_RNG_unchanged=torch.equal(before_cuda,torch.cuda.get_rng_state()),extra_validation_seconds=time.perf_counter()-t)
                write(out/'NATIVE_CACHE_EQUIVALENCE.json',proof)
                if not passed or not proof['cpu_RNG_unchanged'] or not proof['cuda_RNG_unchanged']:
                    raise RuntimeError('Live native prior and precomputed cache are not bitwise identical')
            return value
        # Model constructors still run natively in every arm. Cached forwards were
        # proven not to consume RNG; no per-arm initializer is skipped.
        motion.predict_metric_depth=cached_depth
        write(out/'CHILD_STAGE.json',dict(stage='LOAD_CANDIDATE_EXTENSION'))
        spec=importlib.util.spec_from_file_location('task011b_cadp_dr_c3414af6',str(TASK/'build_001/task011b_cadp_dr_c3414af6.so'))
        candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
        write(out/'CHILD_STAGE.json',dict(stage='INSTALL_CONTROLLER'))
        regression=None
        if arm=='A0' and window==json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows'][0]['window_id']:
            from validate_native import verify
            regression=lambda args,native,module:verify(args,native,module,TASK/'native_regression/real_first_local_001')
        install(self.video,candidate,arm_config(arm),coefficients,out/'native_ba_calls.jsonl',regression)
        original_call=Frontend.__call__;original_second=Frontend.initialize_second_stage
        def frontend_call(frontend,*args,**kwargs):
            frontend.video._task011b_phase=MAIN if frontend.is_initialized else 'INITIALIZATION'
            return original_call(frontend,*args,**kwargs)
        def frontend_second(frontend,*args,**kwargs):
            frontend.video._task011b_phase='INITIALIZATION_SECOND_STAGE'
            return original_second(frontend,*args,**kwargs)
        Frontend.__call__=frontend_call;Frontend.initialize_second_stage=frontend_second
        self.video._task011b_phase='INITIALIZATION'
        write(out/'CHILD_STAGE.json',dict(stage='NATIVE_TRACKER_ENTRY'))
        torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
        super().tracking(pipe)
        if not self.final_clean:raise RuntimeError('Native child did not finish')
        write(out/'TRACKING_CHILD_COMPLETE.json',dict(status='COMPLETE',seconds=time.perf_counter()-start,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            frames=64,keyframes=int(self.video.counter.value),arm=arm,window=window))

    def backend(self):
        self.video._task011b_phase='FINAL_GLOBAL_BA'
        result=super().backend();self.video._task011b_phase='TRAJECTORY_FILLER';return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',required=True);p.add_argument('--arm',required=True);a=p.parse_args()
    torch.multiprocessing.set_start_method('spawn',force=True)
    out=TASK/'runs'/a.window/a.arm;out.mkdir(parents=True,exist_ok=False)
    write(out/'ATTEMPT.json',dict(status='STARTED',window=a.window,arm=a.arm,frames=64))
    cfg=config(a.window,out);setup_seed(43);torch.set_num_threads(4)
    import yaml
    (out/'native_config.yaml').write_text(yaml.safe_dump(cfg))
    stream=stream_class()(cfg,a.window)
    model=ObservedSLAM(cfg,stream);model.task_out=out;model.task_window=a.window;model.task_arm=a.arm
    started=time.perf_counter()
    processes=[];old_process=torch.multiprocessing.Process
    def remember_process(*args,**kwargs):
        proc=old_process(*args,**kwargs);processes.append(proc);return proc
    torch.multiprocessing.Process=remember_process
    try:model.run()
    finally:
        torch.multiprocessing.Process=old_process
        write(out/'PROCESS_EXIT_CODES.json',[dict(pid=p.pid,exit_code=p.exitcode) for p in processes])
    if not (out/'TRACKING_CHILD_COMPLETE.json').is_file():raise RuntimeError('Native tracking child failed; preserve attempt')
    poses=np.atleast_2d(np.loadtxt(out/'native/traj/est_poses_full.txt'))
    if poses.shape!=(64,8) or not np.array_equal(poses[:,0],np.arange(64)) or not np.isfinite(poses).all():
        raise RuntimeError('Native full trajectory is incomplete')
    np.savez_compressed(out/'trajectory.npz',rgb_ids=np.array(stream.ids),c2w_xyzw=poses[:,1:])
    write(out/'COMPLETE.json',dict(status='COMPLETE',seconds=time.perf_counter()-started,frames=64,
        trajectory_sha256=sha(out/'trajectory.npz'),window=a.window,arm=a.arm))
    print('WINDOW_COMPLETE',a.window,a.arm,flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        traceback.print_exc();raise
