"""Diagnostic of the actual ConfigDict subgraph; never a full-model/C0 gate."""
import hashlib,json,os,sys,time,traceback
from pathlib import Path
ROOT=Path('/root/rivermind-data/DROID_W_TASK004C_B_CONFIGDICT_CLOSURE_20261124_R1')
sys.path[:0]=[str(ROOT),str(ROOT/'source_candidate')]
import torch
from native_control.snapshot import ObjectEncoder,read_manifest,load_state,FORMAT
from native_control.configdict_adapter import TAG
from control_common import canonical,digest
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
OUT=ROOT/'cpu_tests/REAL_CONFIGDICT_SUBGRAPH_R1';OUT.mkdir(exist_ok=False)
SOURCE=ROOT/'cpu_tests/REAL_MODEL_ROUNDTRIP_R1/corrected_cpu_snapshot'
started=time.time()
def refs(x):
 if isinstance(x,dict):
  if set(x)=={'$ref'}:yield x['$ref']
  else:
   for v in x.values():yield from refs(v)
 elif isinstance(x,(tuple,list)):
  for v in x:yield from refs(v)
def normalize(root,nodes):
 ids={};out={}
 def rec(x):
  if isinstance(x,dict):
   if set(x)=={'$ref'}:
    old=x['$ref']
    if old not in ids:
     nid='n'+str(len(ids));ids[old]=nid;out[nid]=None;out[nid]=rec(nodes[old])
    return {'$ref':ids[old]}
   return {k:rec(v) for k,v in sorted(x.items())}
  if isinstance(x,(tuple,list)):return [rec(v) for v in x]
  return x
 nr=rec(root);return nr,out
try:
 original=read_manifest(SOURCE)
 config_ids=[k for k,n in original['nodes'].items() if n['kind']==TAG]
 assert len(config_ids)==6
 reach=set();pending=list(config_ids)
 while pending:
  n=pending.pop()
  if n in reach:continue
  reach.add(n);pending.extend(refs(original['nodes'][n]))
 nodes={k:original['nodes'][k] for k in reach}
 assert not any(n.get('class')=='timm.layers.format:Format' for n in nodes.values())
 assert not any(n['kind']=='tensor' for n in nodes.values())
 wrapper='diagnostic_root';nodes[wrapper]={'kind':'list','items':[{'$ref':k} for k in config_ids]}
 classes={n['class']:original['classes'][n['class']] for n in nodes.values() if n.get('class')}
 root={'$ref':wrapper}
 derived={'schema':FORMAT,'endianness':sys.byteorder,'root':root,'nodes':nodes,'classes':classes,'storages':{},'files':{},'provenance':{'artifact_kind':'REAL_CONFIGDICT_SUBGRAPH_DIAGNOSTIC_ONLY','full_model_gate':False,'source_state_sha256':original['state_sha256'],'source_configdict_node_ids':config_ids}}
 derived['state_sha256']=digest(derived)
 destination=OUT/'derived_configdict_only';destination.mkdir()
 raw=canonical(derived);(destination/'manifest.json').write_bytes(raw)
 (destination/'COMPLETE.json').write_bytes(canonical({'manifest_sha256':hashlib.sha256(raw).hexdigest()}))
 restored,loaded=load_state(destination,expected_sha=derived['state_sha256'])
 enc=ObjectEncoder();newroot=enc.encode(restored)
 assert normalize(root,nodes)==normalize(newroot,enc.nodes)
 result={'status':'PASS','source_ConfigDict_nodes':len(config_ids),'reachable_graph_nodes':len(nodes)-1,'exact_mapping_and_attribute_graph_equal':True,'nested_types_order_alias_cycles_preserved':True,'source_snapshot_unchanged':read_manifest(SOURCE)==original,'full_model_restore_passed':False,'full_forward_outputs_restored':False,'native_C0':False,'CUDA_initialized':torch.cuda.is_initialized(),'runtime_seconds':time.time()-started,'source_state_sha256':original['state_sha256'],'derived_subgraph_sha256':derived['state_sha256'],'limitation':'Only exact actual model ConfigDict subgraph; independent FiT3D Format blocker remains'}
 (OUT/'REAL_CONFIGDICT_SUBGRAPH_RECEIPT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except BaseException:
 (OUT/'FAILURE.json').write_text(json.dumps({'traceback':traceback.format_exc(),'CUDA_initialized':torch.cuda.is_initialized()},indent=2));raise
