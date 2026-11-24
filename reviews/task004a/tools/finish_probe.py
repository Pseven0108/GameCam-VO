import os, sys, json, pathlib, ast
p=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(p/'tools'))
from transport import rpc
j=json.loads((p/'bootstrap/evidence/orchestration.json').read_text())
print('BOOTSTRAP_EVENTS',[(k,{x:v for x,v in a.items() if x in ('pid','child','parent','exe','cwd','command','status','failure','after_listeners','after_rerun_processes','temporary_directory_removed')}) for k,a in j.get('remote_events',j.get('events',{})).items()])
print('LOCAL_FILES',[(str(f.relative_to(p)),f.stat().st_size) for folder in ['results','evaluation'] for f in (p/folder).rglob('*') if f.is_file()])
for f in ['release/tools/endpoints.py','release/tools/trace_audit.py','release/tools/contracts.py','release/tools/attempt_contract.py','release/tools/archive.py']:
 text=(p/f).read_text();tree=ast.parse(text)
 print('API',f,[(n.name,ast.unparse(n.args),n.lineno,n.end_lineno) for n in tree.body if isinstance(n,ast.FunctionDef)])
 if 'endpoints.py' in f:print(text[text.find('def evaluate'):][:8000])
 if 'contracts.py' in f:print(text[:5500])
r=rpc("""
import pathlib,json,hashlib,os,socket
p=pathlib.Path('/root/rivermind-data/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
files=[{'path':str(x.relative_to(p)),'bytes':x.stat().st_size} for x in p.rglob('*') if x.is_file() and (str(x.relative_to(p)).startswith('results/') or x.parent==p)]
proc=[]
for d in pathlib.Path('/proc').iterdir():
 if not d.name.isdigit():continue
 try:
  cmd=(d/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  if 'rerun' in cmd or 'task004' in cmd.lower():
   proc.append({'pid':int(d.name),'exe':os.readlink(d/'exe'),'cwd':os.readlink(d/'cwd'),'cmdline':cmd,'stat':(d/'stat').read_text()})
 except (OSError,ProcessLookupError):pass
ports=[]
for tab in ['tcp','tcp6']:
 for row in pathlib.Path('/proc/net/'+tab).read_text().splitlines()[1:]:
  v=row.split();port=int(v[1].split(':')[1],16)
  if v[3]=='0A' and port in (9875,9876,9877):ports.append({'table':tab,'local':v[1],'inode':v[9]})
print(json.dumps({'hostname':socket.gethostname(),'files':files,'bytes':sum(f['bytes'] for f in files),'processes':proc,'ports':ports},ensure_ascii=False))
""",'finish_remote_inventory',timeout=240)
d=json.loads(r);(p/'evidence/finish_remote_inventory.json').write_text(json.dumps(d,indent=2),encoding='utf-8');print('REMOTE_TOTAL',d['bytes'],'FILES',len(d['files']));print('REMOTE_GROUPS',sorted(set(f['path'].split('/')[1] for f in d['files'] if f['path'].startswith('results/'))));print('REMOTE_PROCESSES',d['processes']);print('PORTS',d['ports'])