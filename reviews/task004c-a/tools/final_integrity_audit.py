from transport import *
H=ROOT.parent
ref=json.loads((A/'release/REFERENCE_FILES.json').read_text(encoding='utf8'))
pins=json.loads((A/'release/SOURCE_PINS.json').read_text(encoding='utf8'))['entries']
base=json.loads((ROOT/'evidence/QUICK_RECHECK.stdout.txt').read_text(encoding='utf8'))
historical=json.loads((H/'evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json').read_text(encoding='utf8'))
old={}
for arm in ['E0','E1']:
 meta=historical[arm]['small_metadata'];rd=meta['LAUNCH_RECEIPT.json']['output_dir']
 for f in ['observer.jsonl','native/video.npz','native_config.yaml','trajectory.npz']:
  old[rd+'/'+f]=meta['_TASK004A_ARCHIVE_MANIFEST.json']['files'][f]['sha256']
payload={'auth':AUTH,'source_dir':ref['sources'][0]['source_dir'],'pins':pins,'locked_files':{f:hashlib.sha256(t.encode()).hexdigest() for f,t in base['source_files'].items()},'old':old}
code=r'''
import sys,json,pathlib,hashlib,shutil,subprocess,time
p=json.loads(sys.stdin.readline());auth=p['auth'];r=pathlib.Path(auth['remote_root']);out={'utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
def sha(q):
 h=hashlib.sha256()
 with pathlib.Path(q).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def check(q,e):
 a=sha(q);return dict(path=str(q),expected_sha256=e,actual_sha256=a,match=a==e)
out['frozen_original_source']=[check(pathlib.Path(p['source_dir'])/f,v['sha256']) for f,v in p['pins'].items() if 'sha256' in v]
out['locked_execution_source']=[check(pathlib.Path(auth['lock']['source'])/f,e) for f,e in p['locked_files'].items()]
out['weights_config_extension']=[check(f,e) for f,e in auth['lock']['pins'].items()]
out['historical_results']=[check(f,e) for f,e in p['old'].items()]
out['new_statuses']={}
for d in ['captures/E0','captures/E1','replays/E0_D1','replays/E0_D0','replays/E1_D1','replays/E1_D0']:
 q=json.loads((r/d/'STATUS.json').read_text());assert q['phase']=='complete' and q['exit_code']==0;out['new_statuses'][d]={'phase':q['phase'],'exit_code':q['exit_code'],'elapsed':q['elapsed']}
out['new_file_inventory']=[dict(path=str(q.relative_to(r)),bytes=q.stat().st_size) for q in sorted(r.rglob('*')) if q.is_file() and not q.is_symlink() and 'archives' not in q.parts and '__pycache__' not in q.parts]
out['raw_bytes_total']=sum(x['bytes'] for x in out['new_file_inventory'])
out['all_protected_matches']=all(x['match'] for k in ['frozen_original_source','locked_execution_source','weights_config_extension','historical_results'] for x in out[k]);assert out['all_protected_matches']
for name,cmd in [('gpu',['nvidia-smi','--query-gpu=name,memory.total,memory.free,memory.used','--format=csv,noheader,nounits']),('gpu_compute_apps',['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])]:
 q=subprocess.run(cmd,capture_output=True,text=True,timeout=20);out[name]=dict(exit_code=q.returncode,stdout=q.stdout,stderr=q.stderr)
out['data_free_bytes']=shutil.disk_usage('/root/rivermind-data').free
out['shm_free_bytes']=shutil.disk_usage('/dev/shm').free
out['shutdown']=False;out['reboot']=False;out['no_new_gpu_computation_in_this_audit']=True
print(json.dumps(out))
'''
r=remote(code,payload,'FINAL_INTEGRITY_AUDIT',180)
(ROOT/'evidence/FINAL_INTEGRITY_AUDIT.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'all_protected_matches':r['all_protected_matches'],'source_count':len(r['frozen_original_source']),'new_bytes':r['raw_bytes_total'],'data_free_bytes':r['data_free_bytes'],'gpu':r['gpu'],'compute_apps':r['gpu_compute_apps'],'largest_files':sorted(r['new_file_inventory'],key=lambda x:x['bytes'],reverse=True)[:8]},indent=2))
