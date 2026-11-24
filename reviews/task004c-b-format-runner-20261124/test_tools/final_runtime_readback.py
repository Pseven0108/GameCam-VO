from remote_cpu import ROOT,call
import json
code=r'''
import hashlib,json,pathlib,subprocess,shutil,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');s=r/'source_candidate'
items=[]
for name in ('capture','restore_check'):
 a=r/'attempts'/name
 files=[{'file':str(p.relative_to(a)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in a.rglob('*.rrd')]
 items.append({'mode':name,'rrd_files':files,'browser_render_verified':False,'all_stage_succeeded':(a/'SUCCESS.json').is_file()})
rows=[]
for p in sorted((r/'attempts').glob('*/shared_cpu/*')):
 if p.is_file():rows.append({'path':str(p.relative_to(r)),'bytes':p.stat().st_size,'mode':oct(p.stat().st_mode&0o777),'inode':p.stat().st_ino,'retained':True})
m=json.loads((r/'C0/manifest.json').read_text());complete=json.loads((r/'C0/COMPLETE.json').read_text())
assert hashlib.sha256((r/'C0/manifest.json').read_bytes()).hexdigest()==complete['manifest_sha256']
report={'time_unix':time.time(),'native_Rerun':items,'new_Arena_file_count':len(rows),'new_Arena_bytes':sum(x['bytes'] for x in rows),'Arena_retained_no_cleanup':rows,'C0_metadata_unchanged':True,'C0_state_sha256':m['state_sha256'],'data_disk_free_bytes':shutil.disk_usage(r).free,'GPU_compute_apps':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],text=True),'source_commit':subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip(),'source_worktree_clean':not subprocess.check_output(['git','-C',str(s),'status','--porcelain'],text=True).strip(),'instance_running':True,'instance_shutdown':False,'no_automatic_retry':True}
(r/'evidence/FINAL_RUNTIME_STATE.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='Arena_retained_no_cleanup'}))
'''
out=call('FINAL_GPU_IDLE_C0_METADATA_READBACK_R1',code,timeout=120)
(ROOT/'evidence/FINAL_RUNTIME_STATE_SUMMARY.json').write_text(out);print(out)
