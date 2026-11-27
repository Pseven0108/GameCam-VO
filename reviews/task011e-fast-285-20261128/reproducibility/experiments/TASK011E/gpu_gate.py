"""Single fast RTX3090 adapter/identity check. No models or BA are run."""
import hashlib,importlib.util,json,shutil,subprocess,sys,types
from pathlib import Path
import numpy as np
import torch

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def main(x):
    root=Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
    source=root/'source/DROID-W'
    assert torch.__version__=='2.1.0+cu118',torch.__version__
    assert '3090' in torch.cuda.get_device_name(0)
    proc=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
    # This is called before this process performs its first tensor allocation.
    assert not proc, 'Another CUDA process already exists: '+proc
    torch.cuda.init();torch.set_num_threads(4)
    u=types.ModuleType('adapter');u.__file__='/tmp/task011e_adapter_not_imported_from_disk.py'
    exec(compile(x['adapter'],u.__file__,'exec'),u.__dict__)
    a=types.ModuleType('audit');exec(compile(x['audit'],'transfer_audit.py','exec'),a.__dict__)
    rng=np.random.default_rng(20261128);records=[]
    for count in (7,32):
        coeff=rng.uniform(.01,.99,(64,45,80)).astype(np.float32)
        valid=rng.random(coeff.shape)>.12;coeff[~valid]=0
        mon=np.ones((500,45,80),np.float32);mon[rng.random(mon.shape)<.1]=0
        v=types.SimpleNamespace(counter=types.SimpleNamespace(value=64),
            timestamp=torch.arange(64,device='cuda').float().flip(0),
            disps=torch.ones((500,45,80),device='cuda'))
        args=[None]*30;args[3]=torch.as_tensor(mon,device='cuda')
        args[11]=torch.arange(count,device='cuda',dtype=torch.long);args[13:15]=[0,count]
        cache=torch.as_tensor(coeff,device='cuda');nv=torch.as_tensor(valid,device='cuda')
        with a.TransferAudit() as audit:out,proof=u.gather_source_strength(v,args,cache,nv)
        torch.cuda.synchronize();trans=audit.report()
        assert not trans['full_buffer_pixel_D2H'] and not trans['CUDA_scalar_reads']
        assert trans['explicit_D2H_bytes']==(count+1)*14*8
        assert proof['reduction_dtype']=='torch.float32'
        assert max(r['absolute_mean_difference'] for r in proof['frames'])<=1e-6
        host=out.cpu().numpy()
        for slot in range(count):
            ts=63-slot;mask=valid[ts]&(mon[slot]>0)
            assert np.max(np.abs(host[slot][mask]-coeff[ts][mask].mean(dtype=np.float64)))<=1e-6
            assert np.all(host[slot][~mask]==0)
        assert np.all(host[count:]==0)
        records.append(dict(sources=count,proof=proof,transfer_audit=trans))
    sys.path.insert(0,str(source));import droid_backends
    original=Path(droid_backends.__file__)
    candidate=Path('/root/rivermind-data/GAMECAM_TASK011B_20261127_AMP_NATIVE_R2/build_001/task011b_cadp_dr_c3414af6.so')
    assert digest(candidate)==x['candidate_sha256']
    spec=importlib.util.spec_from_file_location('task011b_cadp_dr_c3414af6',candidate)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert callable(module.ba) and callable(droid_backends.ba)
    weights=[]
    for r in x['weight_requests']:
        p=root/r['relative_path'];h=digest(p)
        assert h==r['expected_sha256'],r['name']
        weights.append(dict(name=r['name'],path=str(p),bytes=p.stat().st_size,sha256=h,load_source=r['load_source']))
    report=dict(status='PASS',torch=torch.__version__,cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(0),free_vram_bytes=torch.cuda.mem_get_info()[0],
        disk_free_bytes=shutil.disk_usage('/root/rivermind-data').free,
        shm_free_bytes=shutil.disk_usage('/dev/shm').free,adapter=records,
        original_extension=dict(path=str(original),sha256=digest(original),bytes=original.stat().st_size),
        candidate_extension=dict(path=str(candidate),sha256=digest(candidate),bytes=candidate.stat().st_size),
        native_BA_calls=0,model_forwards=0)
    print(json.dumps(dict(preflight=report,model_identity=dict(status='VERIFIED_EXISTING_WEIGHTS',weights=weights,
        actual_configuration='frozen_r2.yaml',unloaded_models_not_required=True))))

if __name__=='__main__':main(json.load(sys.stdin))
