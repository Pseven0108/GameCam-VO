from transport import *
import ast
for p in (ROOT/'tools').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
files={n:base64.b64encode((ROOT/'tools'/n).read_bytes()).decode() for n in ('remote_one.py','remote_control.py')}
viewer=json.loads((A/'bootstrap/evidence/BOOTSTRAP_PASS.json').read_text())['viewer']['native_identity']['argv']
code=r'''import sys,json,pathlib,base64,hashlib,subprocess,os,shutil
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);d=root/'control';assert not d.exists();d.mkdir()
for n,data in s['files'].items():
 b=base64.b64decode(data);compile(b,n,'exec');(d/n).write_bytes(b)
(d/'CONTROL_CONFIG.json').write_text(json.dumps(dict(viewer_argv=s['viewer_argv']),indent=2))
lock=json.loads((root/'evidence/LOCKDOWN.json').read_text());manifest=pathlib.Path(lock['manifest']);doc=json.loads(manifest.read_text())
for row in doc['frames']:
 p=(manifest.parent/row['file']).resolve();assert p.stat().st_size==row['bytes'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],row['rgb_id']
assert shutil.disk_usage(root).free>=s['storage_required']
report=dict(files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()},rgb_verified=len(doc['frames']))
(root/'evidence/CONTROL_RELEASE_VERIFICATION.json').write_text(json.dumps(report,indent=2))
with (root/'evidence/controller.stdout.txt').open('xb') as out,(root/'evidence/controller.stderr.txt').open('xb') as err:
 p=subprocess.Popen(['/usr/bin/python3','-I','-B','-u',str(d/'remote_control.py'),str(root)],stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),start_new_session=True)
 receipt=dict(pid=p.pid,root=str(root),new_gpu_run_budget=16,no_retry=True,detached_controller=True)
 (root/'evidence/CONTROLLER_LAUNCH.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
sto=json.loads((ROOT/'evidence/STORAGE_PREFLIGHT_V2.json').read_text())
r=rpc(code,dict(root=REMOTE,files=files,viewer_argv=viewer,storage_required=sto['remote_required']),'START_TASK004B_AUTHORIZED_16_RUNS',timeout=120)
put(ROOT/'evidence/CONTROLLER_LAUNCH.json',r);print(json.dumps(r))
