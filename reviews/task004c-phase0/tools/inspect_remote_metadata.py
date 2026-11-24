import sys,pathlib,json,base64,subprocess,shlex
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
sys.path.insert(0,str(A/'bootstrap'))
from run_once import ssh_base,HOST,CREATE,verified
pre=json.loads((A/'bootstrap/evidence/preflight.json').read_text());lock=json.loads((ROOT/'evidence/HISTORICAL_IDENTITY_REFERENCE.json').read_text());ref=json.loads((A/'release/REFERENCE_FILES.json').read_text());pins=json.loads((A/'release/SOURCE_PINS.json').read_text())
old=json.loads((ROOT/'evidence/PHASE0_REMOTE.json').read_text())
payload=dict(lock=lock,original_source=ref['sources'][0]['source_dir'],source_pins=pins['entries'],npz_paths=[i['path'] for i in old['checkpoint_inventory'] if '/results/E0/' in i['path'] or '/results/E1/' in i['path']],A_name=A.name,compiler=ref['compiler'])
CODE=r'''
import sys,os,pathlib,json,zipfile,struct,ast,hashlib,subprocess
p=json.loads(sys.stdin.readline());r={}
def sha(x):
 h=hashlib.sha256()
 with open(x,'rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def cmd(args):
 try:
  c=subprocess.run(args,capture_output=True,text=True,timeout=25);return dict(command=args,exit_code=c.returncode,stdout=c.stdout,stderr=c.stderr)
 except Exception as e:return dict(error=repr(e))
def headers(x):
 d=dict(path=x,bytes=os.stat(x).st_size,sha256=sha(x),arrays=[])
 with zipfile.ZipFile(x) as z:
  for i in z.infolist():
   a=dict(name=i.filename,bytes=i.file_size,crc32=f'{i.CRC:08x}')
   if i.filename.endswith('.npy'):
    with z.open(i) as f:
     magic=f.read(6);version=tuple(f.read(2));assert magic==b'\x93NUMPY'
     n=struct.unpack('<H' if version==(1,0) else '<I',f.read(2 if version==(1,0) else 4))[0]
     a['header']=ast.literal_eval(f.read(n).decode('utf-8' if version==(3,0) else 'latin1').strip())
   d['arrays'].append(a)
 return d
r['npz']=[headers(x) for x in p['npz_paths']]
r['original_git']=cmd(['git','-C',p['original_source'],'rev-parse','HEAD']);r['original_status']=cmd(['git','-C',p['original_source'],'status','--porcelain']);r['source_verification']=[]
for rel,e in p['source_pins'].items():
 if 'sha256' in e:
  q=pathlib.Path(p['original_source'])/rel;r['source_verification'].append(dict(relative_path=rel,expected_sha256=e['sha256'],actual_sha256=sha(q) if q.is_file() else None,match=q.is_file() and sha(q)==e['sha256']))
r['compiler']=cmd([p['compiler'],'--version'])
r['torch_build_static']=[]
env=pathlib.Path(p['lock']['python']).parents[1]
for x in env.glob('lib/python*/site-packages/torch/version.py'):r['torch_build_static'].append(dict(path=str(x),source=x.read_text()))
r['source_files']={}
for root in [p['lock']['source'],'/root/rivermind-data/'+p['A_name']+'/source']:
 for rel in ['src/depth_video.py','src/factor_graph.py','src/frontend.py','src/slam.py','src/lib/droid.cpp']:
  q=pathlib.Path(root)/rel
  if q.is_file():r['source_files'][str(q)]=dict(sha256=sha(q),text=q.read_text())
for root in [p['lock']['pipeline'],'/root/rivermind-data/'+p['A_name']+'/pipeline']:
 r.setdefault('pipeline_catalog',{})[root]=sorted(os.listdir(root))
 for q in pathlib.Path(root).glob('*.py'):
  if any(s in q.name for s in ['observer','controls','run_segment']):r['source_files'][str(q)]=dict(sha256=sha(q),text=q.read_text())
r['legacy_candidates']=[];r['legacy_npz']=[]
for root in pathlib.Path('/root/rivermind-data').iterdir():
 if root.is_dir() and any(s in root.name for s in ['BA280','STAGE_OBSERVABILITY','TASK004']):
  r['legacy_candidates'].append(str(root))
  if 'BA280' in root.name:
   for q in root.glob('inputs/*.npz'):r['legacy_npz'].append(headers(str(q)))
print(json.dumps(r,allow_nan=False))
'''
loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<task004c-npz-metadata-and-static-source>','exec'))"
command='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
q=subprocess.run(ssh_base(pre)+['-o','ClearAllForwardings=yes',HOST,command],input=base64.b64encode(CODE.encode())+b'\n'+json.dumps(payload).encode()+b'\n',capture_output=True,creationflags=CREATE,timeout=200)
err=ROOT/'evidence/PHASE0_EXTRA.ssh.stderr.txt';err.write_bytes(q.stderr);(ROOT/'evidence/PHASE0_EXTRA.stdout.txt').write_bytes(q.stdout);trust=verified(err)
(ROOT/'evidence/PHASE0_EXTRA_PROCESS.json').write_text(json.dumps(dict(exit_code=q.returncode,trust=trust,utc=datetime.now(timezone.utc).isoformat()),indent=2))
assert q.returncode==0 and all(trust.values()),(q.returncode,q.stderr.decode(errors='replace')[-1000:],q.stdout.decode(errors='replace')[-1000:])
r=json.loads(q.stdout);(ROOT/'evidence/PHASE0_EXTRA.json').write_text(json.dumps(r,indent=2))
print(json.dumps(dict(original_git=r['original_git'],original_status=r['original_status'],source_files_verified=sum(v['match'] for v in r['source_verification']),source_files_total=len(r['source_verification']),npz=[dict(path=v['path'],arrays={x['name']:x.get('header',{}) for x in v['arrays']}) for v in r['npz']],legacy=r['legacy_candidates']),indent=2))
