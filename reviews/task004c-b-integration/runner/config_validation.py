import json,pathlib
import yaml
from control_common import ControlError
class UniqueLoader(yaml.SafeLoader):pass
def unique_mapping(loader,node,deep=False):
    out={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if key in out:raise ControlError('Duplicate YAML key: '+str(key))
        out[key]=loader.construct_object(value_node,deep=deep)
    return out
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)
MATRIX={'B1':(1,'S1','record'),'B2':(0,'S1','replay'),'B3':(1,'S0','replay'),'B4':(0,'S0','record')}
def load_and_validate(path,identity_lock):
    c=yaml.load(pathlib.Path(path).read_text(),Loader=UniqueLoader);arm=c.get('experiment');lock=identity_lock
    if arm not in MATRIX:raise ControlError('Explicit B1/B2/B3/B4 required')
    expected={'schema':'GAMECAM_CROSSOVER_CONFIG_V1','experiment':arm,'D':MATRIX[arm][0],'W':1,'U':1,'init_D':0,
        'schedule':MATRIX[arm][1],'schedule_mode':MATRIX[arm][2],'c0_ref':lock['c0_ref'],
        'schedule_ref':'artifacts/'+MATRIX[arm][1]+'.jsonl','intervention_scope':'frontend_mainloop_local_ba',
        'final_ba':'native_unchanged','filler':'native_unchanged',**lock['fixed'],
        **{k:lock[k] for k in ('baseline_commit','r2_yaml_sha256','extension_sha256','input_manifest_sha256')}}
    if c!=expected or any(type(c[k]) is not int for k in ('D','W','U','init_D','frames','width','height','stride','buffer','seed')):raise ControlError('Frozen configuration changed')
    return c
