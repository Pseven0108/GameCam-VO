import json
from remote_cpu import ROOT,call
code=r'''
import ast,hashlib,json,pathlib
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
p=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub/yvanyin_metric3d_main/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py')
raw=p.read_bytes();text=raw.decode();tree=ast.parse(text);lines=text.splitlines();classes=[]
for cls in tree.body:
 if isinstance(cls,ast.ClassDef) and cls.name in ('LoRALayer','LoRALinear'):
  lambdas=[]
  for node in ast.walk(cls):
   if isinstance(node,ast.Lambda):
    args=[a.arg for a in node.args.args]
    lambdas.append({'line':node.lineno,'AST':ast.dump(node,include_attributes=False),
      'is_single_argument_identity':len(args)==1 and isinstance(node.body,ast.Name) and node.body.id==args[0]})
  classes.append({'name':cls.name,'line':cls.lineno,'end_line':cls.end_lineno,'lambdas':lambdas,
    'source_excerpt':'\n'.join('%d: %s'%(i+1,lines[i]) for i in range(cls.lineno-1,cls.end_lineno))})
result={'scope':'STATIC_READ_ONLY_NO_MODEL_INIT','path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),
 'classes':classes,'GPU_runs_added':0,'runtime_callable_object_not_available_after_exit':True,
 'identity_assignment_explanation':'Source-based inference, not a recovered runtime closure'}
(root/'artifacts/CLOSURE_BASE_CLASS_EVIDENCE.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
'''
d=json.loads(call('CLOSURE_BASE_CLASS_SOURCE',code,timeout=30))
(ROOT/'evidence/CLOSURE_BASE_CLASS_EVIDENCE.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
