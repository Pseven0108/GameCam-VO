"""Reuse frozen lossless storage serializer; add only the BA-input provenance kind."""
import inspect,hashlib,ast
from native_control import snapshot
ORIGINAL=inspect.getsource(snapshot.prepare_state)
OLD="('CPU_NATIVE_INTERFACE_FIXTURE','NATIVE_C0')"
NEW="('CPU_NATIVE_INTERFACE_FIXTURE','NATIVE_C0','TASK005B_REAL_BA_INPUT')"
if ORIGINAL.count(OLD)!=1:raise RuntimeError('Snapshot provenance anchor changed')
ns=dict(snapshot.__dict__);exec(compile(ORIGINAL.replace(OLD,NEW),'<task005b-ba-storage-kind>','exec'),ns)
def prepare_ba_state(payload,provenance,destination_parent):
 if provenance.get('artifact_kind')!='TASK005B_REAL_BA_INPUT' or not provenance.get('freshly_recaptured'):raise RuntimeError('BA provenance incomplete')
 return ns['prepare_state'](payload,provenance=provenance,destination_parent=destination_parent)
ADAPTER_RECEIPT={'original_sha256':hashlib.sha256(ORIGINAL.encode()).hexdigest(),'effective_sha256':hashlib.sha256(ORIGINAL.replace(OLD,NEW).encode()).hexdigest(),'change':'allow one separate BA-input provenance kind; storage serialization unchanged'}
