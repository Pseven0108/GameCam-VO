"""Reuse the existing verified SSH identity, retaining separate cleanup receipts."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parents[1]/'experiments/task008_pi3mos/scripts/remote_transport.py'
spec=importlib.util.spec_from_file_location('task008_verified_transport',SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
mod.ROOT=ROOT
if __name__=='__main__':
    p=Path(sys.argv[1]);label=sys.argv[2]
    result=mod.run(p.read_text('utf-8'),label,timeout=int(sys.argv[3]) if len(sys.argv)>3 else 240)
    (ROOT/(label+'.json')).write_text(result,encoding='utf-8')
    if label.startswith('inventory'):
        data=json.loads(result)
        print(json.dumps({'hostname':data['hostname'],'volumes':data['volumes'],'target_inventory':data['target_inventory'],
                          'processes':data['processes'],'gpu':data['gpu'],'gpu_processes':data['gpu_processes'],
                          'other_data_root_names':[x['name'] for x in data['data_root_entries'] if not any(t in x['name'].lower() for t in ['task008','pi3mos'])]},ensure_ascii=False,indent=2))
    else:print(result)
