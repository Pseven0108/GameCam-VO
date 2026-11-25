import hashlib,json,pathlib,subprocess
BASE=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
HUB=BASE/'data/torch_hub/yvanyin_metric3d_main'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def rec(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
out={'root':str(BASE),'root_listing':[x.name for x in BASE.iterdir()],
     'hub':str(HUB),'hub_exists':HUB.is_dir(),'hub_git_exists':(HUB/'.git').exists(),
     'code_files':[],'weights':[],'model_deserialized':False}
if HUB.is_dir():
 for p in sorted(HUB.rglob('*')):
  if p.is_file() and not any(x in p.parts for x in ['__pycache__','.git']):
   b=p.read_bytes()
   out['code_files'].append({'rel':p.relative_to(HUB).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
      'git_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()})
 p=HUB/'.git'
 if p.exists():
  out['hub_HEAD']=subprocess.check_output(['git','-C',str(HUB),'rev-parse','HEAD'],text=True).strip()
for p in [BASE/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth',
          BASE/'source/DROID-W/src/utils/mono_priors/metric_depth_estimators.py']:
 if p.is_file():out['weights' if p.suffix=='.pth' else 'baseline_entry']=out.get('weights' if p.suffix=='.pth' else 'baseline_entry',[])+[rec(p)]
out['identity_text']={}
for rel in ['evidence/official-source-lock.json','source/DROID-W/configs/droid_w.yaml']:
 p=BASE/rel
 if p.is_file():out['identity_text'][rel]=p.read_text()[:12000]
print(json.dumps(out,indent=2))
