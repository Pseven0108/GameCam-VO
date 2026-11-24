import json,pathlib
from remote_cpu import ROOT,call
code=r'''
import json,pathlib
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1/source_candidate')
m=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main')
paths={'metric_base':m/'mono/model/model_pipelines/__base_model__.py','metric_pipeline':m/'mono/model/model_pipelines/dense_pipeline.py','factorgraph':r/'src/factor_graph.py','filler':r/'src/trajectory_filler.py','observer':r/'task003_observer.py','timer':r/'src/utils/sys_timer.py','droid_net':r/'src/modules/droid_net/droid_net.py'}
print(json.dumps({k:p.read_text() for k,p in paths.items()}))
'''
d=json.loads(call('INSPECT_RUNTIME_MISC',code))
for n,v in d.items():(ROOT/'source_intake'/(n+'.py')).write_text(v,encoding='utf-8')
print(d['metric_base']);print(d['metric_pipeline']);print(d['droid_net'][:5000]);print(d['factorgraph'][:4000]);print(d['timer'][:2500])
