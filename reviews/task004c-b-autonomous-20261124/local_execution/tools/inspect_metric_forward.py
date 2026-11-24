import json
from remote_cpu import ROOT,call
code=r'''
import pathlib,json
p=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py')
print(json.dumps({'text':p.read_text()}))
'''
d=json.loads(call('INSPECT_METRIC_FORWARD',code));(ROOT/'source_intake/metric_decoder_full.py').write_text(d['text'],encoding='utf-8')
for a,b in [(750,870),(875,1012)]:print('\n'.join(f'{i+1}: {s}' for i,s in enumerate(d['text'].splitlines()) if a<=i+1<=b))
