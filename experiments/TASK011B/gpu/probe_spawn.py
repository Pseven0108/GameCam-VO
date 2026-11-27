"""No inference: reproduce native video CUDA-IPC transport with buffer500."""
import faulthandler
faulthandler.enable()
from runtime import *
import torch,torch.multiprocessing as mp
from src.slam import SLAM
from src.utils.common import setup_seed


def child(video):
    print('SPAWN_CHILD_ENTERED',flush=True)
    print('CUDA_SUM',float(video.disps[:1].sum().item()),flush=True)
    print('CPU_SHAPE',tuple(video.images.shape),flush=True)
    with video.get_lock():print('COUNTER_LOCK_OK',video.counter.value,flush=True)


if __name__=='__main__':
    mp.set_start_method('spawn',force=True)
    out=TASK/'transport_probe';out.mkdir(exist_ok=False)
    cfg=config('val_001_00207-00270',out);setup_seed(43)
    stream=stream_class()(cfg,'val_001_00207-00270');model=SLAM(cfg,stream)
    mp.set_start_method('spawn',force=True)
    p=mp.Process(target=child,args=(model.video,));p.start();p.join()
    write(out/'PROBE_RECEIPT.json',dict(child_exit_code=p.exitcode,model_inference=False,BA_run=False,buffer=500))
    model.printer.terminate();print('CHILD_EXIT',p.exitcode,flush=True)
