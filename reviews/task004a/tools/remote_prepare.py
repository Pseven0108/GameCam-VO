import base64,hashlib,io,json,os,pathlib,shutil,socket,subprocess,sys,tarfile,time
spec=json.loads(sys.stdin.readline());root=pathlib.Path(spec['root']);refs=spec['refs'];pins=spec['source']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def command(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=30);assert p.returncode==0,(args,p.stderr);return p.stdout
assert socket.gethostname()==refs['hostname']
assert not root.exists(),'campaign already exists; cannot restart'
sm=command(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'])
assert 'RTX 3090' in sm and int(sm.strip().split(',')[-1])>=23000
assert not command(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits']).strip(),'GPU is occupied'
free=shutil.disk_usage('/root/rivermind-data').free;shm=shutil.disk_usage('/dev/shm').free
assert free>=37*1024**3 and shm>=8*1024**3
memory=pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip();assert memory=='max' or int(memory)>=32*1024**3
verified=[]
for r in refs['files']:
    p=pathlib.Path(r['path']);assert p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],r['path'];verified.append(r)
base=pathlib.Path(refs['sources'][0]['source_dir']);n=0
for name,row in pins['entries'].items():
    if 'sha256' in row:assert sha(base/name)==row['sha256'],name;n+=1
assert n==208
manifest=next(pathlib.Path(r['path']) for r in refs['files'] if r['label']=='487-frame RGB manifest with fixed K')
doc=json.loads(manifest.read_bytes());assert [f['rgb_id'] for f in doc['frames']]==list(range(1,488))
for frame in doc['frames']:
    p=(manifest.parent/frame['file']).resolve(strict=True);assert p.stat().st_size==frame['bytes'] and sha(p)==frame['sha256'],str(p)
root.mkdir();(root/'results').mkdir();(root/'evidence').mkdir();(root/'release').mkdir()
blob=base64.b64decode(spec['release_tar_b64'])
with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as t:
    for m in t.getmembers():
        p=(root/'release'/m.name).resolve();assert p.is_relative_to(root/'release') and m.isfile(),m.name
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
release_pins=json.loads((root/'release/RELEASE_SHA256.json').read_bytes())
for name,value in release_pins.items():assert sha(root/'release'/name)==value,name
# Copy the already approved isolated Task003 source, never modify it in place.
source=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/source/DROID-W')
shutil.copytree(source,root/'source',symlinks=True,ignore=shutil.ignore_patterns('__pycache__','.git'))
preview=root/'release/candidates/preview'
for p in preview.rglob('*'):
    if p.is_file():target=root/'source'/p.relative_to(preview);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
shutil.copyfile(root/'release/candidates/task004_controls.py',root/'source/task004_controls.py')
pipe=root/'pipeline';pipe.mkdir()
for name in ['task004_run_segment.py']:
    shutil.copyfile(root/'release/candidates'/name,pipe/name)
for name in ['segment_input.py','transfer_common.py']:
    shutil.copyfile(pathlib.Path('/root/rivermind-data/DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/pipeline')/name,pipe/name)
# Authentication-aware runtime remains fail-closed; no model is imported here.
lock=dict(root=str(root),source=str(root/'source'),pipeline=str(pipe),manifest=str(manifest),config=str(root/'release/candidates/r2_sealed_config.yaml'),python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',weights=[r['path'] for r in refs['files'] if r['label'] in ['droid.pth','dinov2_reg_small_finetuned.pth','metric_depth_vit_large_800k.pth','model.safetensors']],extension=str(root/'source/droid_backends.cpython-310-x86_64-linux-gnu.so'),torch_home='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub',hf_home='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface')
lock['pins']={str(p):sha(p) for parent in [pipe,root/'source'] for p in parent.rglob('*') if p.is_file() and (p.suffix in ['.py','.yaml','.so'] or p.name=='task004_controls.py')}
lock['pins'].update({r['path']:r['sha256'] for r in refs['files'] if r['path'] in lock['weights']})
lock['pins'][str(manifest)]=sha(manifest);lock['pins'][lock['config']]=sha(pathlib.Path(lock['config']))
(root/'evidence/LOCKDOWN.json').write_text(json.dumps(lock,indent=2))
report=dict(status='PASS',hostname=socket.gethostname(),gpu=sm.strip(),data_free_bytes=free,shm_free_bytes=shm,cgroup_memory_max=memory,source_blobs_verified=n,rgb_hashes_verified=len(doc['frames']),reference_files_verified=len(verified),four_weights_verified=len(lock['weights']),release_files_verified=len(release_pins),cuda_initialized=False,model_constructed=False,root=str(root))
(root/'evidence/PREFLIGHT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
