"""Close only this task's monitors after all four arms, then summarize measured resources."""
import json,pathlib,sys
from remote import ROOT,call
code=r'''
import pathlib,json,time,os,hashlib,shutil
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
for arm in ('B1','B2','B4','B3'):
 p=r/'attempts'/arm
 assert (p/'SUCCESS.json').is_file() and json.loads((p/'PROCESS_RECEIPT.json').read_text())['exit_code']==0
stopped=[]
for base in (r,r.with_name('DROID_W_TASK004C_B_IO_COMPAT_20261124_R2_READY')):
 receipt=json.loads((base/'evidence/RESOURCE_MONITOR_STARTED.json').read_text());pid=receipt['pid']
 proc=pathlib.Path('/proc')/str(pid);cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode() if proc.exists() else ''
 if proc.exists():assert str(base/'resource_monitor.py') in cmd,(pid,cmd)
 stop=base/'evidence/RESOURCE_MONITOR_STOP'
 assert not stop.exists();stop.write_text('All four R3 arms complete; stop task-owned monitor only.\n')
 for _ in range(40):
  if not proc.exists() or (proc/'stat').read_text().split()[2]=='Z':break
  time.sleep(.25)
 alive=proc.exists() and (proc/'stat').read_text().split()[2]!='Z'
 assert not alive,pid
 stopped.append({'workspace':str(base),'monitor_pid':pid,'monitor_cmdline':cmd,'stop_marker':str(stop),'exited':True})
records=[json.loads(x) for x in (r/'evidence/RESOURCE_TIMELINE.jsonl').read_text().splitlines()]
threshold=10*1024**3
bad=[x for x in records if x['disk_free_bytes']<threshold];episodes=[];active=[]
for i,x in enumerate(records):
 if x['disk_free_bytes']<threshold:active.append((i,x))
 elif active:
  episodes.append({'first_sample_unix':active[0][1]['unix'],'last_sample_unix':active[-1][1]['unix'],'next_recovered_sample_unix':x['unix'],'observed_bad_samples':len(active),'minimum_free_bytes':min(a['disk_free_bytes'] for _,a in active),'sampled_duration_upper_approx_s':x['unix']-active[0][1]['unix']});active=[]
if active:episodes.append({'first_sample_unix':active[0][1]['unix'],'last_sample_unix':active[-1][1]['unix'],'observed_bad_samples':len(active),'minimum_free_bytes':min(a['disk_free_bytes'] for _,a in active),'ongoing_at_final_sample':True})
stages={}
for arm in ('B1','B2','B4','B3'):
 rr=[x for x in records if arm in x['stages_in_progress']]
 gpu=[]
 for x in rr:
  if x['gpu_exit']==0:
   vals=x['gpu_csv'].split(',')
   if len(vals)==3:gpu.append([float(z.strip()) for z in vals])
 stages[arm]={'samples':len(rr),'first_sample_unix':rr[0]['unix'],'last_sample_unix':rr[-1]['unix'],'gpu_peak_used_MiB_sampled':max(v[0] for v in gpu) if gpu else None,'GPU_memory_includes_Rerun_and_process_overhead':True,'minimum_data_free_bytes':min(x['disk_free_bytes'] for x in rr),'max_shm_used_bytes':max(x['shm_used_bytes'] for x in rr),'max_cgroup_current_bytes_sampled':max(x.get('cgroup_current',0) for x in rr)}
raw=(r/'evidence/RESOURCE_TIMELINE.jsonl').read_bytes()
report={'scope':'Current R3 four-arm monitor; 5 second target sampling interval','records':len(records),'first_sample_unix':records[0]['unix'],'last_sample_unix':records[-1]['unix'],'max_observed_sampling_gap_s':max(b['unix']-a['unix'] for a,b in zip(records,records[1:])),'timeline_sha256':hashlib.sha256(raw).hexdigest(),'disk_floor_bytes':threshold,'data_disk_floor_held_continuously':False if bad else 'NO_BREACH_OBSERVED_AT_SAMPLED_TIMES','bad_samples':len(bad),'disk_breach_episodes':episodes,'minimum_data_free_bytes':min(x['disk_free_bytes'] for x in records),'duration_is_sampled_approximation':True,'stages':stages,'owned_monitors_stopped':stopped,'server_shutdown':False,'server_rebooted':False,'final_data_free_bytes':shutil.disk_usage(r).free,'final_system_free_bytes':shutil.disk_usage('/root').free,'final_shm_free_bytes':shutil.disk_usage('/dev/shm').free,'model_processes_started_by_this_tool':0}
with (r/'evidence/FINAL_RESOURCE_AUDIT.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
'''
a=call('R3_FINAL_RESOURCE_AUDIT_01',code,timeout=90)
(ROOT/'evidence/R3_FINAL_RESOURCE_AUDIT_01.json').write_text(json.dumps(a,indent=2))
print(json.dumps(a,indent=2))
