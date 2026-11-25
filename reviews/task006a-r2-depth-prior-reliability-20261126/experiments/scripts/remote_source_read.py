import hashlib,json,pathlib
base=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
hub=base/'data/torch_hub/yvanyin_metric3d_main'
paths=['LICENSE','hubconf.py','mono/model/monodepth_model.py','mono/model/model_pipelines/__base_model__.py',
 'mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py',
 'mono/configs/HourglassDecoder/vit.raft5.large.py',
 'mono/configs/_base_/models/encoder_decoder/dino_vit_large_reg.dpt_raft.py',
 'training/mono/configs/RAFTDecoder/vit.raft5.large.py',
 'training/mono/model/losses/GRUSequenceLoss.py']
files=[]
for rel in paths:
 p=hub/rel;b=p.read_bytes()
 files.append({'rel':rel,'source':str(p),'sha256':hashlib.sha256(b).hexdigest(),'content':b.decode('utf-8')})
p=base/'source/DROID-W/src/utils/mono_priors/metric_depth_estimators.py';b=p.read_bytes()
files.append({'rel':'DROID-W-runtime/metric_depth_estimators.py','source':str(p),'sha256':hashlib.sha256(b).hexdigest(),'content':b.decode('utf-8')})
print(json.dumps({'files':files,'model_imported':False},ensure_ascii=True))
