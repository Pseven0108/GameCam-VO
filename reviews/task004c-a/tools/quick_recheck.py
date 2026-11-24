from transport import *
code=r'''
import sys,json,pathlib,shutil,hashlib,subprocess,time
p=json.loads(sys.stdin.readline());r={}
def cmd(a):
 q=subprocess.run(a,capture_output=True,text=True,timeout=20);return {'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
r['hostname']=cmd(['hostname']);r['gpu']=cmd(['nvidia-smi','--query-gpu=index,name,uuid,memory.total,memory.free','--format=csv,noheader,nounits']);r['gpu_processes']=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])
for n,x in [('data','/root/rivermind-data'),('shm','/dev/shm')]:
 u=shutil.disk_usage(x);r[n]={'total':u.total,'free':u.free}
r['pins']={}
for f,sha in p['lock']['pins'].items():
 q=pathlib.Path(f);h=hashlib.file_digest(q.open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(q.read_bytes()).hexdigest();r['pins'][f]={'sha256':h,'match':h==sha}
r['source_files']={}
for f in ['src/slam.py','src/tracker.py','src/frontend.py','src/factor_graph.py','src/depth_video.py','src/lib/droid_kernels.cu','src/lib/droid.cpp','src/geom/projective_ops.py','task003_observer.py','task004_controls.py']:
 q=pathlib.Path(p['lock']['source'])/f
 if q.is_file():r['source_files'][f]=q.read_text()
r['pipeline_files']={}
for f in pathlib.Path(p['lock']['pipeline']).glob('*.py'):
 if f.name in ['task004_run_segment.py','run_segment.py','segment_input.py','transfer_common.py']:r['pipeline_files'][f.name]=f.read_text()
r['configuration']=pathlib.Path(p['lock']['config']).read_text()
print(json.dumps(r))
'''
r=remote(code,AUTH,'QUICK_RECHECK',180)
for f,s in r.pop('source_files').items():
 q=ROOT/'source'/f;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8')
for f,s in r.pop('pipeline_files').items():(ROOT/'source'/f).write_text(s,encoding='utf8')
(ROOT/'evidence/QUICK_RECHECK.json').write_text(json.dumps(r,indent=2))
print(json.dumps({k:v for k,v in r.items() if k not in ['configuration','pins']},indent=2));print('PIN_MATCH',all(v['match'] for v in r['pins'].values()))
