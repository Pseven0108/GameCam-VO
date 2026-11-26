"""Standalone CPU-only PyTorch restoration of archived canonical outputs.

No model imports, checkpoint deserialization, CUDA queries, or inference. This
script runs in the existing torch environment with CUDA_VISIBLE_DEVICES empty.
"""
import hashlib,json,os,pathlib,shutil,time
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import numpy as np
import torch
import torch.nn.functional as F

OLD=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1')
OUT=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_2_CPU_RESTORE_20261126_R1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:f.write(json.dumps(x,indent=2,allow_nan=False)+'\n')
def main():
    started=time.perf_counter();OUT.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    if shutil.disk_usage(OUT).free<10*1024**3+200*1024**2: raise RuntimeError('Preserve 10GiB free plus output budget')
    results=[]
    for sub in ['smoke_qualified','pilot']:
        receipt=json.loads((OLD/sub/'INFERENCE_RECEIPT.json').read_text())
        assert receipt['status']=='PASS'
        for row in receipt['results']:
            p=OLD/sub/pathlib.PurePosixPath(row['output']).name
            if sha(p)!=row['sha256']:raise RuntimeError('Archived input identity mismatch')
            sid=row['sample']['sample_id'];arrays={};stats=[]
            with np.load(p,allow_pickle=False) as z:
                for mode in ['native','flip']:
                    original=z[mode+'_canonical_depth'];a=torch.from_numpy(original.copy())[None,None]
                    assert a.device.type=='cpu'
                    l,t,r,b=row['padding_ltrb'];h,w=row['canonical_hw'];a=a[:,:,t:h-b,l:w-r]
                    target=row['sample']['input_hw'];fx=row['sample']['fx'];factor=fx/1000
                    cubic=F.interpolate(a,target,mode='bicubic',align_corners=False)[0,0].numpy()*factor
                    linear=F.interpolate(a,target,mode='bilinear',align_corners=False)[0,0].numpy()*factor
                    official=linear*row['resize_scale']
                    for name,value in [('bilinear_same_focal_unclipped',linear),('bilinear_same_focal',np.clip(linear,0,300)),
                                       ('bilinear_official_focal_unclipped',official),('bilinear_official_focal',np.clip(official,0,300)),
                                       ('bicubic_CPU_unclipped',cubic)]:arrays[mode+'_'+name]=value
                    old=z[mode+'_depth_unclipped'];delta=np.abs(cubic.astype(float)-old.astype(float))
                    c=torch.from_numpy(z[mode+'_canonical_confidence'].copy())[None,None]
                    c=c[:,:,t:h-b,l:w-r]
                    cn=F.interpolate(c,target,mode='bilinear',align_corners=False)[0,0].numpy()
                    arrays[mode+'_confidence_CPU']=cn
                    stats.append({'mode':mode,'canonical_min':float(original.min()),'bicubic_CPU_min':float(cubic.min()),
                         'bicubic_CPU_vs_saved_GPU_max_abs':float(delta.max()),'bicubic_CPU_vs_saved_GPU_mean_abs':float(delta.mean()),
                         'bicubic_CPU_vs_saved_GPU_allclose':bool(np.allclose(cubic,old,atol=2e-4,rtol=2e-4)),
                         'confidence_CPU_vs_saved_GPU_max_abs':float(np.abs(cn-z[mode+'_confidence']).max()),
                         'linear_min':float(linear.min()),'linear_nonpositive':int((linear<=0).sum()),
                         'official_scale_ratio':row['resize_scale']})
            dest=OUT/(sid+'.npz');np.savez_compressed(dest,**arrays)
            results.append({'sample_id':sid,'source_sha256':sha(p),'output':str(dest),'sha256':sha(dest),'bytes':dest.stat().st_size,'comparisons':stats})
            print('RESTORED',sid,flush=True)
    # Self-contained CPU fixtures exercise singleton borders, non-integer ratios,
    # odd padding and a positive discontinuity that can overshoot with bicubic.
    rng=np.random.default_rng(43);fixtures={};fixture_rows=[]
    for j,(shape,target) in enumerate([((1,1),(3,7)),((1,4),(3,11)),((4,1),(11,3)),((3,5),(7,9)),((7,9),(3,4)),((8,12),(8,12))]):
        a=rng.uniform(.01,100,shape).astype('float32');b=F.interpolate(torch.from_numpy(a)[None,None],target,mode='bilinear',align_corners=False)[0,0].numpy()
        fixtures[f'input_{j}']=a;fixtures[f'output_{j}']=b;fixture_rows.append({'id':j,'input_shape':list(shape),'output_shape':list(target)})
    np.savez_compressed(OUT/'CPU_INTERPOLATION_FIXTURES.npz',**fixtures)
    dump(OUT/'CPU_RESTORE_RECEIPT.json',{'status':'PASS','torch':torch.__version__,'device':'cpu',
      'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'model_forwards':0,'checkpoint_deserialized':False,
      'elapsed_seconds':time.perf_counter()-started,'script_sha256':sha(pathlib.Path(__file__)) if pathlib.Path(__file__).is_file() else None,
      'results':results,'fixtures':fixture_rows,'free_bytes_after':shutil.disk_usage(OUT).free})
    print('CPU_RESTORE_COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
