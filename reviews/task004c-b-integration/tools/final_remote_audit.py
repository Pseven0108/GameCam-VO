"""Final read-only source/input protection and stdlib GPU gate; CPU demo only."""
import base64,hashlib,io,json,pathlib,sys,zipfile
from remote_access import ROOT,run
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_INTEGRATION_20261124_R1'
LABEL=sys.argv[1] if len(sys.argv)>1 else 'release'
safe=json.loads((ROOT/'evidence/PHASE0_REVIEW_SAFE.json').read_text())
lock=json.loads((ROOT/'configs/identity_lock.json').read_text())
payload={'baseline':safe['source_manifest'],'lock':lock,'cpu_demo_code':(ROOT/'tools/cpu_demo.py').read_text(),
         'expected_upload':json.loads(zipfile.ZipFile(ROOT/'artifacts'/('CANDIDATE_UPLOAD_'+LABEL+'.zip')).read('UPLOAD_SHA.json'))}
code=r'''
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import ast,base64,hashlib,io,json,pathlib,shutil,socket,subprocess,sys,zipfile
p=json.load(sys.stdin);root=pathlib.Path(REMOTE_ROOT);label=LABEL_REPLACEMENT;assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
sys.path.insert(0,str(root))
from native_control.admission import preflight
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
source=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/source')
rows=[]
for row in p['baseline']:
 path=source/row['path']
 match=(path.is_symlink() and os.readlink(path)==row['target']) if row['kind']=='symlink' else (path.is_file() and sha(path)==row['sha256'])
 rows.append({'path':row['path'],'match':match})
assert all(x['match'] for x in rows),'Original execution source changed'
upload={name:sha(root/name)==expected for name,expected in p['expected_upload'].items()};assert all(upload.values())
input_path=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json')
assert sha(input_path)==p['lock']['input_manifest_sha256']
doc=json.loads(input_path.read_text());rgb=[]
for frame in doc['frames']:
 path=input_path.parent/frame['file'];actual=sha(path);expected=frame.get('sha256',frame.get('rgb_sha256'))
 rgb.append({'rgb_id':frame['rgb_id'],'file':str(path),'sha256':actual,'expected_sha256':expected,'match':actual==expected if expected else None})
assert len(rgb)==487 and [x['rgb_id'] for x in rgb]==list(range(1,488))
assert all(x['match'] is not False for x in rgb)
cpu=root/'artifacts'/('CPU_SUITE_'+label)/'CPU_TEST_REPORT.json'
report=json.loads(cpu.read_text());assert report['total']==report['passed'] and not report['cuda_initialized']
syntax=[]
for folder in ['native_control','runner','checkpoint','schedule']:
 for file in (root/folder).glob('*.py'):compile(file.read_text(),str(file),'exec');syntax.append(str(file.relative_to(root)))
candidate_pins={name:expected for name,expected in p['expected_upload'].items() if name.endswith('.py') and not name.startswith(('tests/','source_before/'))}
for row in p['baseline']:
 if row['kind']=='file':
  name='source_candidate/'+row['path'];expected=p['expected_upload'].get(name,row['sha256'])
  assert sha(root/name)==expected,'Candidate frozen source differs outside declared patch: '+name
  candidate_pins[name]=expected
token={'cpu_report_sha256':sha(cpu),'candidate_pins':candidate_pins,'native_real_validation_passed':False,
       'formal_B_runs_authorized':False,'max_rgb':80,'scope':'BOUNDED_NATIVE_VALIDATION_ONLY_AFTER_LIVE_RESOURCE_ADMISSION'}
(root/'evidence').mkdir(exist_ok=True)
release=root/'evidence/CPU_NATIVE_RELEASE.json'
if release.exists():
 history=root/'evidence/release_history';history.mkdir(exist_ok=True)
 old=history/(sha(release)+'.json')
 if not old.exists():shutil.copy2(release,old)
with release.open('w') as f:json.dump(token,f,indent=2)
admission=preflight(root,p['lock'],cpu_report=cpu)
admission['current_mode_user_confirmed']='NO_CARD_STARTUP'
with (root/'evidence'/('GPU_ADMISSION_'+label+'.json')).open('x') as f:json.dump(admission,f,indent=2)
(root/'tools').mkdir(exist_ok=True);demo=root/'tools/cpu_demo.py';demo.write_text(p['cpu_demo_code'])
q=subprocess.run([sys.executable,'-B',str(demo),label],cwd=root,capture_output=True,timeout=90,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'))
(root/'artifacts'/('CPU_DEMO_'+label+'.stdout.txt')).write_bytes(q.stdout);(root/'artifacts'/('CPU_DEMO_'+label+'.stderr.txt')).write_bytes(q.stderr)
assert q.returncode==0,q.stderr.decode(errors='replace')
demo_receipt=json.loads(q.stdout);assert not demo_receipt['cuda_initialized']
git=lambda *a:subprocess.run(['git','-C',str(root/'source_candidate'),*a],capture_output=True,text=True,check=True).stdout.strip()
result={'hostname':socket.gethostname(),'original_source_compared':len(rows),'original_source_unchanged':sum(x['match'] for x in rows),
        'original_source_results':rows,'uploaded_candidate_files_verified':len(upload),'uploaded_candidate_all_match':all(upload.values()),
        'input_manifest_sha256':sha(input_path),'rgb_files':rgb,'rgb_sha_matches':sum(x['match'] is True for x in rgb),
        'rgb_sha_without_manifest_reference':sum(x['match'] is None for x in rgb),
        'protected_assets_match':all(x['match'] for x in admission['protected_pins'].values()),
        'candidate_git_commit':git('rev-parse','HEAD'),'candidate_git_status':git('status','--porcelain=v1','-uno'),
        'baseline_candidate_git_commit':(root/'BASELINE_GIT_COMMIT.txt').read_text(),
        'admission':admission,'cpu_tests':{k:v for k,v in report.items() if k!='tests'},'syntax_files_verified':syntax,
        'cpu_demo':demo_receipt,'cpu_demo_exit_code':q.returncode,
        'models_started':0,'native_C0_captures':0,'native_GPU_restore_count':0,'formal_experiments':0,
        'free_bytes_after':shutil.disk_usage(root).free}
with (root/'evidence'/('FINAL_PROTECTION_'+label+'.json')).open('x') as f:json.dump(result,f,indent=2)
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for n in ['evidence/CPU_NATIVE_RELEASE.json','evidence/GPU_ADMISSION_'+label+'.json','artifacts/CPU_DEMO_'+label+'.stdout.txt','artifacts/CPU_DEMO_'+label+'.stderr.txt']:
  z.write(root/n,n)
 for f in (root/'artifacts'/('CPU_INSPECTABLE_FIXTURE_'+label)).rglob('*'):
  if f.is_file():z.write(f,f.relative_to(root).as_posix())
result['demo_zip_b64']=base64.b64encode(b.getvalue()).decode()
print(json.dumps(result))
'''.replace('REMOTE_ROOT',repr(REMOTE)).replace('LABEL_REPLACEMENT',repr(LABEL))
r=json.loads(run('FINAL_REMOTE_PROTECTION_'+LABEL,code,timeout=240,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',input_bytes=json.dumps(payload).encode()))
archive=base64.b64decode(r.pop('demo_zip_b64'));target=ROOT/'evidence'/('CPU_DEMONSTRATION_'+LABEL);target.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        dest=target/n;assert dest.resolve().is_relative_to(target.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))
(ROOT/'evidence'/('FINAL_PROTECTION_'+LABEL+'.json')).write_text(json.dumps(r,indent=2))
(ROOT/'evidence'/('CPU_NATIVE_RELEASE_'+LABEL+'.json')).write_bytes((target/'evidence/CPU_NATIVE_RELEASE.json').read_bytes())
(ROOT/'evidence'/('GPU_ADMISSION_'+LABEL+'.json')).write_bytes((target/('evidence/GPU_ADMISSION_'+LABEL+'.json')).read_bytes())
print(json.dumps({k:r[k] for k in ['original_source_compared','original_source_unchanged','uploaded_candidate_files_verified','rgb_sha_matches','rgb_sha_without_manifest_reference','protected_assets_match','candidate_git_commit','candidate_git_status','models_started','formal_experiments','free_bytes_after']}))
print(json.dumps({'gpu_admitted':r['admission']['admitted'],'issues':r['admission']['issues'],'cpu_demo':r['cpu_demo']}))
