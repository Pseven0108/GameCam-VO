"""New-process serial native runs with CPU-only forkserver imports cached once.

The GPU probe and every actual experiment are distinct child processes. No
models, CUDA context, CUDA tensors, random states or video buffers are reused.
"""
import json
import multiprocessing as mp
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def cpu_probe(path):
    import torch
    import task010_native_preload as preload
    result={**preload.STATUS,'probe_child_pid':os.getpid(),
            'CUDA_initialized_in_child':torch.cuda.is_initialized(),
            'CUDA_bad_fork_in_child':torch.cuda._is_in_bad_fork()}
    if result['CUDA_initialized_in_child'] or result['CUDA_bad_fork_in_child']:
        raise RuntimeError('Forkserver failed CPU-only CUDA contract')
    Path(path).write_text(json.dumps(result,indent=2))


def gpu_probe(path):
    import torch
    if torch.cuda._is_in_bad_fork() or torch.cuda.is_initialized():raise RuntimeError('Child has inherited CUDA state')
    x=torch.arange(32,device='cuda',dtype=torch.float32)
    if float((x*x).sum())!=10416.:raise RuntimeError('CUDA child computation failed')
    torch.cuda.synchronize()
    result={'status':'PASS','child_pid':os.getpid(),'fresh_CUDA_context':True,
            'GPU':torch.cuda.get_device_name(0),'no_model_loaded':True}
    Path(path).write_text(json.dumps(result,indent=2))


def execute(script,args,log_path):
    # Keep the file open through exception recording. An earlier observer-only
    # admission failed before any model/BA; the original wrapper hid its error
    # by trying to print a traceback to an already closed stream.
    tempfile.tempdir=os.environ.get('TMPDIR','/mnt/d/aaa/tmp/gamecam-vo')
    with Path(log_path).open('x',encoding='utf-8',buffering=1) as log:
        os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
        sys.stdout=log;sys.stderr=log
        try:
            script=str((ROOT/script).resolve())
            if not Path(script).is_relative_to(ROOT):raise RuntimeError('Script escaped task workspace')
            print('ENTER_FRESH_CHILD',os.getpid(),script,flush=True)
            import torch
            if torch.cuda._is_in_bad_fork() or torch.cuda.is_initialized():raise RuntimeError('GPU state inherited before experiment')
            sys.argv=[script,*args]
            runpy.run_path(script,run_name='__main__')
        except BaseException:
            traceback.print_exc(file=log);log.flush();raise


def main():
    # NVML availability checks avoid initializing CUDA in AMP decorators during preload.
    os.environ['PYTORCH_NVML_BASED_CUDA_CHECK']='1'
    # DrvFs cannot bind AF_UNIX sockets (the recorded first probe failed ENOTSUP).
    # This directory contains IPC sockets only, no weights, datasets or results.
    ipc=Path('/dev/shm')/('task010a-forkserver-'+str(os.getpid()))
    ipc.mkdir(mode=0o700)
    tempfile.tempdir=str(ipc)
    mp.set_forkserver_preload(['task010_native_preload'])
    ctx=mp.get_context('forkserver')
    cpu_path=TASK/'09_reproducibility/FORKSERVER_HOLDOUT_CPU_ADMISSION.json'
    child=ctx.Process(target=cpu_probe,args=(str(cpu_path),));child.start();child.join()
    if child.exitcode:raise RuntimeError('CPU forkserver admission failed; no GPU experiment launched')
    print('CPU_FORKSERVER_READY_NO_GPU_WAITING_FOR_FROZEN_PLAN',flush=True)
    ready=TASK/'private/FORKSERVER_HOLDOUT_READY.json';deadline=time.monotonic()+4*3600
    while not ready.exists():
        if time.monotonic()>deadline:raise RuntimeError('No frozen transfer plan; stopping CPU server')
        time.sleep(2)
    plan=json.loads(ready.read_text())
    gpu_path=TASK/'09_reproducibility/FORKSERVER_HOLDOUT_GPU_ADMISSION.json'
    child=ctx.Process(target=gpu_probe,args=(str(gpu_path),));child.start();child.join()
    if child.exitcode:raise RuntimeError('GPU forkserver admission failed; no native run launched')
    state={'status':'STARTED','start_method':'forkserver_CPU_preload_only','plan':plan,'jobs':[]}
    path=TASK/'private/forkserver_holdout_STATE.json'
    for job in plan['jobs']:
        if shutil.disk_usage(ROOT).free<15*1024**3:raise RuntimeError('D: reserve below15GiB')
        record={'id':job['id'],'status':'RUNNING','started':time.time(),'fresh_child_process':True}
        state['jobs'].append(record);path.write_text(json.dumps(state,indent=2))
        child=ctx.Process(target=execute,args=(job['script'],job['args'],str(TASK/'private'/('job_'+job['id']+'.log'))))
        child.start();record['pid']=child.pid;path.write_text(json.dumps(state,indent=2))
        print('FORKSERVER_START',job['id'],child.pid,flush=True)
        with (TASK/'private'/('resources_'+job['id']+'.jsonl')).open('x') as monitor:
            while child.is_alive():
                q=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
                monitor.write(json.dumps({'elapsed':time.time()-record['started'],'whole_GPU_memory_utilization':q.stdout.strip()})+'\n');monitor.flush();time.sleep(1)
        child.join();record.update(status='COMPLETE' if child.exitcode==0 else 'FAILED',exit_code=child.exitcode,seconds=time.time()-record['started'])
        if child.exitcode:
            state['status']='STOPPED_ON_FAILURE';path.write_text(json.dumps(state,indent=2));raise RuntimeError('Native child failed; no retry or skip')
        path.write_text(json.dumps(state,indent=2));print('FORKSERVER_END',job['id'],record['seconds'],flush=True)
    state['status']='COMPLETE';path.write_text(json.dumps(state,indent=2))


if __name__=='__main__':main()
