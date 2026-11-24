from transport import *
code=r'''
import sys,json,pathlib,shutil,subprocess,datetime
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'GPU_kept_online':True,'shutdown':False,'reboot':False,'data_free_bytes':shutil.disk_usage(r).free}
for name,args in [('gpu',['nvidia-smi','--query-gpu=name,memory.free,memory.used','--format=csv,noheader,nounits']),('compute_apps',['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])]:
 c=subprocess.run(args,capture_output=True,text=True,timeout=20);out[name]={'exit_code':c.returncode,'stdout':c.stdout,'stderr':c.stderr}
out['archive_status']=json.loads((r/'archives/RAW_ARCHIVE_STATUS.json').read_text())['phase'];out['new_model_or_BA_execution']=False
print(json.dumps(out))
'''
r=remote(code,{'root':AUTH['remote_root']},'END_STATE_READONLY',60);(ROOT/'evidence/END_STATE_READONLY.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r,indent=2))
