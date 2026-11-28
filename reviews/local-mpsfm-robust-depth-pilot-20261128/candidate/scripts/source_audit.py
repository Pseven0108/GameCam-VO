"""CPU provenance check, with no access to the remote experiment."""
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
PROJECT=pathlib.Path('D:/aaa/GameCam-VO')
FROZEN=pathlib.Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')
COMMIT='c3414af6047d06bafc1a6645d09f23247f3b2cdc'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()
def main():
    target=TASK/'reports/SOURCE_AND_ASSET_AUDIT_V2.json'
    if target.exists():raise FileExistsError(target)
    listing=subprocess.check_output(['git','-C',str(FROZEN),'ls-tree','-r',COMMIT],text=True)
    records=[]
    for line in listing.splitlines():
        ident,name=line.split('\t',1);mode,kind,oid=ident.split()
        if kind!='blob':continue
        p=ROOT/'upstream/DROID-W'/name
        if not p.exists():
            records.append(dict(path=name,kind=kind,mode=mode,status='NOT_EXPORTED_SYMLINK' if mode=='120000' else 'MISSING'))
            continue
        raw=p.read_bytes();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        normalized=raw.replace(b'\r\n',b'\n')
        norm_oid=hashlib.sha1(b'blob '+str(len(normalized)).encode()+b'\0'+normalized).hexdigest()
        records.append(dict(path=name,expected_git_blob=oid,actual_git_blob=actual,
            byte_exact=actual==oid,normalized_lf_git_blob=norm_oid,match=actual==oid or norm_oid==oid))
    files=['weights/droid.pth','torch_home/hub/checkpoints/metric_depth_vit_large_800k.pth',
           'torch_home/hub/checkpoints/dinov2_reg_small_finetuned.pth']
    assets=PROJECT/'data/sota_assets/DROID_W'
    weights=[dict(file=n,bytes=(assets/n).stat().st_size,sha256=sha(assets/n)) for n in files]
    comparisons=[]
    for name in ['droid.cpp','droid_kernels.cu','correlation_kernels.cu','altcorr_kernel.cu']:
        old=PROJECT/'baselines/droid_w/upstream/src/lib'/name
        frozen=ROOT/'upstream/DROID-W/src/lib'/name
        a=old.read_text();b=frozen.read_text()
        equivalent=a.replace('.scalar_type()', '.type()')==b
        comparisons.append(dict(file=name,local_43c1425b_source_equals_c3414af6=a==b,
            equals_after_dispatch_API_normalization=equivalent))
    config=pathlib.Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/configs/frozen_r2.yaml')
    out=dict(commit=COMMIT,export_git_blob_checks=records,
        export_all_regular_files_match=all(x.get('match',False) for x in records if x.get('mode')!='120000'),
        weights=weights,read_only_R2_config_sha256=sha(config),
        installed_backend_source_candidate_comparison=comparisons,
        remote_connections=0,shared_assets_were_read_only=True,
        baseline_freeze='No production source, shared checkpoint, YAML or installed extension was written by this task.')
    target.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(files=len(records),all_match=out['export_all_regular_files_match'],weights=len(weights),native_sources=comparisons),indent=2))
if __name__=='__main__':main()
