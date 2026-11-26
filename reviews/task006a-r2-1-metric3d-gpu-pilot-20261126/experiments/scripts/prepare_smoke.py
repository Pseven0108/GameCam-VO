import ast,hashlib,json,pathlib
from remote_io import ROOT,REMOTE_ROOT
project=ROOT.parents[1]
source=project/'experiments/VIPER_MATCHED_DUAL_BASELINE_R2/manifests/val_007_full_00001-00487.json'
m=json.loads(source.read_text());frame=m['frames'][0]
sample={'sample_id':'VIPER_Night_val007_00001','dataset':'VIPER','sequence_id':'val_007','frame_id':'00001',
 'environment':m['environment'],'rgb_path':'/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/val_007/'+frame['file'],
 'rgb_sha256':frame['sha256'],'source_hw':m['raw_wh'][::-1],'input_hw':m['out_wh'][::-1],'fx':m['output_k'][0],
 'source_fx':m['fixed_source_k'][0],'input_protocol':'FROZEN_R2_640x360_INTER_LINEAR','role':'NO_GT_SMOKE_ONLY'}
payload={'samples':[sample],'source_manifest':str(source),'source_manifest_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'GT_error_evaluation_admitted':False}
dst=ROOT/'experiments/configs/SMOKE_MANIFEST.json'
with dst.open('x',encoding='utf-8') as f:f.write(json.dumps(payload,indent=2)+'\n')
for p in (ROOT/'experiments/scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
print(json.dumps({'manifest':str(dst),'samples':1,'source_frame':frame['rgb_id'],'fx':sample['fx']}))
