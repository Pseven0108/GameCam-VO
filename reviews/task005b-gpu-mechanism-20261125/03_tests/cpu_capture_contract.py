import os,sys,pathlib,json,hashlib,ast,io,gzip,subprocess,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];HIST=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');sys.path[:0]=[str(ROOT/'tools'),str(HIST/'source_candidate')]
import torch
from native_control.snapshot import load_state,save_prepared_state
from ba_state_io import prepare_ba_state,ADAPTER_RECEIPT
from prefix_journal import ReadOnlyPrefixJournal
from control_common import digest,canonical
checks=[]
def check(name,ok):
 if not ok:raise RuntimeError('CPU contract failed: '+name)
 checks.append(name)
for name in ['capture_prefix.py','prefix_journal.py','ba_state_io.py']:ast.parse((ROOT/'tools'/name).read_text());check('AST '+name,True)
a=torch.arange(60,dtype=torch.float32).reshape(10,6);b=a[2:7,1::2]
payload={'tensors':{'base':a,'view':b},'scalars':{'iterations':2},'cached_mono':a}
provenance={'artifact_kind':'TASK005B_REAL_BA_INPUT','freshly_recaptured':True,'synthetic_CPU_contract_only':True}
dest=ROOT/'evidence/CPU_STORAGE_FIXTURE'
p=prepare_ba_state(payload,provenance,dest.parent);m=save_prepared_state(p,dest);restored,mm=load_state(dest,allow_cuda=False)
check('alias preserved',restored['tensors']['base'].untyped_storage()._cdata==restored['tensors']['view'].untyped_storage()._cdata)
check('stride preserved',restored['tensors']['view'].stride()==b.stride());check('offset preserved',restored['tensors']['view'].storage_offset()==b.storage_offset());check('dtype and values',torch.equal(b,restored['tensors']['view']) and b.dtype==restored['tensors']['view'].dtype)
check('no CUDA initialized',not torch.cuda.is_initialized());check('all native BA tensors captured',all(x in (ROOT/'tools/capture_prefix.py').read_text() for x in ['cached_mono','affine_weights','dino_feats_resize','rng','slot_rgb_tokens']))
# Tiny hash-chained synthetic prefix exercises the same production replay class.
h={'c0_sha256':'cpu_fixture','init_D':0,'W':1,'U':1,'max_rgb':487,'stage':'formal487','schedule':'S1'}
from native_control.runtime import SCHEMA
rows=[{'type':'header','schema':SCHEMA,'header':h,'sha256':digest(h)}];prev=rows[0]['sha256']
for i,(kind,payload) in enumerate([('frame.begin',{'index':18}),('frame.end',{'next_input_index':19})]):
 e={'type':'event','index':i,'kind':kind,'rgb':19,'context':{},'payload':payload,'previous_sha256':prev};e['sha256']=digest(e);prev=e['sha256'];rows.append(e)
raw=b''.join(canonical(r)+b'\n' for r in rows);f=ROOT/'evidence/CPU_SCHEDULE_FIXTURE.jsonl';f.write_bytes(raw)
j=ReadOnlyPrefixJournal(f,ROOT/'evidence/CPU_SCHEDULE_REPLAY.jsonl',hashlib.sha256(raw).hexdigest(),stop_rgb=19)
j.point('frame.begin',19,{}, {'index':18});j.point('frame.end',19,{}, {'next_input_index':19});check('frozen prefix replay lifecycle',j.finish_prefix()['consumed_events']==2)
report={'PASS':True,'passed':len(checks),'checks':checks,'CUDA_initialized':False,'native_GPU_calls':0,'adapter':ADAPTER_RECEIPT}
(ROOT/'evidence/CPU_CAPTURE_CONTRACT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
