import pathlib,json,hashlib
hub=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main')
out=[]
for p in (hub/'mono/model/backbones').rglob('*.py'):
 s=p.read_text()
 if 'mask_token' in s:
  lines=s.splitlines();hits=[i for i,x in enumerate(lines) if 'mask_token' in x or 'masks=' in x or 'def forward_features' in x]
  out.append({'path':str(p.relative_to(hub)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
              'contexts':[{'line':i+1,'text':'\n'.join(lines[max(0,i-3):i+8])} for i in hits]})
for path in ['mono/model/monodepth_model.py','mono/model/model_pipelines/__base_model__.py','mono/model/backbones/ViT_DINO_reg.py']:
 p=hub/path
 if p.is_file():out.append({'path':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'content':p.read_text()})
print(json.dumps(out,indent=2))
