"""The remote complete commit is the only code baseline for this task."""
import base64,hashlib,io,json,pathlib,shutil,zipfile
from remote_access import ROOT,run
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1'
BASE='0931141cf88247dc8fb0c7628c1d91b6531fea90'
code=r'''
import base64,hashlib,io,json,os,pathlib,shutil,socket,subprocess,zipfile
root=pathlib.Path(NEW_ROOT);base=BASE_COMMIT
old=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_INTEGRATION_20261124_R1');origin=old/'source_candidate'
assert socket.gethostname()=='jupyter-yd6gks8uzfbxzdb4'
def cmd(*a):return subprocess.run(a,capture_output=True,text=True,check=True).stdout.strip()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
assert cmd('git','-C',str(origin),'rev-parse','HEAD')==base,'Wrong complete candidate HEAD'
assert cmd('git','-C',str(origin),'status','--porcelain=v1','-uno')=='','Original candidate is dirty'
assert not root.exists(),'New task must not overwrite earlier output'
root.mkdir();cmd('git','clone','--no-hardlinks','--local',str(origin),str(root/'source_candidate'))
assert cmd('git','-C',str(root/'source_candidate'),'rev-parse','HEAD')==base
cmd('git','-C',str(root/'source_candidate'),'switch','-c','codex/task004c-b-native-release-fixes')
for name in ['native_control','checkpoint','schedule','runner']:(root/name).symlink_to('source_candidate/'+name,target_is_directory=True)
(root/'control_common.py').symlink_to('source_candidate/control_common.py')
for name in ['evidence','logs','artifacts','tools','source_before']:(root/name).mkdir()
for name in ['tests','configs']:shutil.copytree(old/name,root/name,ignore=shutil.ignore_patterns('__pycache__'))
source=root/'source_candidate';source_rows=[];export={}
for p in sorted(source.rglob('*')):
 if '.git' in p.parts or '__pycache__' in p.parts:continue
 rel=p.relative_to(source).as_posix()
 if p.is_symlink():source_rows.append({'path':rel,'kind':'symlink','target':os.readlink(p)})
 elif p.is_file():
  row={'path':rel,'kind':'file','bytes':p.stat().st_size,'sha256':sha(p)};source_rows.append(row)
  if (rel.split('/')[0] in ['native_control','checkpoint','schedule','runner'] and p.suffix=='.py') or rel in ['control_common.py','task004_controls.py'] or (rel.startswith('src/') and p.suffix=='.py'):
   export['baseline_export/'+rel]=p.read_bytes()
for name in ['tests','configs']:
 for p in (root/name).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:export[p.relative_to(root).as_posix()]=p.read_bytes()
# The old full 118-test result is copied verbatim, with its original SHA.
prior=old/'artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json'
assert json.loads(prior.read_text())['passed']==118
export['evidence/ORIGINAL_118_CPU_TEST_REPORT.json']=prior.read_bytes()
old_upload=json.loads((old/'UPLOAD_SHA_handoff.json').read_text())
test_refs={}
for p in (root/'tests').rglob('*.py'):
 rel=p.relative_to(root).as_posix();test_refs[rel]=sha(p)
 assert old_upload[rel]==test_refs[rel],'Original test source no longer matches release'
# Preimages for the original tests come directly from commit093, not Windows.
for name in ['src/depth_video.py','src/factor_graph.py','src/tracker.py','src/slam.py','src/frontend.py','src/trajectory_filler.py','src/backend.py','src/motion_filter.py','src/geom/ba.py','src/modules/droid_net/corr.py','src/utils/droid_visualization_rerun.py','task004_controls.py']:
 p=root/'source_before'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.run(['git','-C',str(source),'show',base+':'+name],capture_output=True,check=True).stdout)
 export['source_before/'+name]=p.read_bytes()
meta={'hostname':socket.gethostname(),'remote_root':str(root),'source_origin':str(origin),'baseline_commit':base,
 'forbidden_local_commit_used':False,'full_candidate_file_manifest':source_rows,'original_tests_sha256':test_refs,
 'original_118_report_sha256':sha(prior),'disk':dict(zip(('total','used','free'),shutil.disk_usage(root))),
 'shm':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),'gpu_queried':False,'CUDA_initialized':False}
(root/'evidence/REMOTE_BASELINE_IDENTITY.json').write_text(json.dumps(meta,indent=2))
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in export.items():z.writestr(name,data)
 z.writestr('evidence/REMOTE_BASELINE_IDENTITY.json',json.dumps(meta,indent=2))
print(json.dumps({'baseline':base,'copied_files':len(source_rows),'root':str(root),'export_zip_b64':base64.b64encode(b.getvalue()).decode()}))
'''.replace('NEW_ROOT',repr(REMOTE)).replace('BASE_COMMIT',repr(BASE))
result=json.loads(run('BASELINE_REMOTE_093',code,timeout=240))
raw=base64.b64decode(result.pop('export_zip_b64'));(ROOT/'evidence/REMOTE_093_BASELINE_EXPORT.zip').write_bytes(raw)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    for name in z.namelist():
        p=ROOT/name;assert p.resolve().is_relative_to(ROOT.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
for p in (ROOT/'baseline_export').rglob('*'):
    if p.is_file():
        dest=ROOT/'candidate'/p.relative_to(ROOT/'baseline_export');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
print(json.dumps(result))
