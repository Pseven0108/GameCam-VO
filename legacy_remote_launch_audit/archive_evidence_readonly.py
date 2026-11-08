"""Archive-time checks only. No torch import, GPU numerical work, model, or data parsing."""
import datetime,hashlib,json,pathlib,subprocess
out=pathlib.Path('/root/rivermind-data/gamecam/setup/K6-A-GPU-R2-LAUNCH-AUDIT')
status=json.loads((out/'final_status.json').read_text())
if not status['passed'] or status['model_execution_authorized'] or status['model_attempts']!=0:raise RuntimeError('Refuse to archive a run with an unexpected status')
p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=5)
(out/'postflight_gpu_processes.stdout.txt').write_text(p.stdout);(out/'postflight_gpu_processes.stderr.txt').write_text(p.stderr)
record={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nvidia_smi_exit_code':p.returncode,'compute_processes_present':bool(p.stdout.strip()),'no_new_GPU_test_run':True,'model_attempts':0,'passed':p.returncode==0 and not p.stdout.strip()}
with (out/'postflight_process_verification.json').open('x') as f:json.dump(record,f,indent=2)
rows=[]
for f in sorted(out.rglob('*')):
    if f.is_file() and f.name!='remote_evidence_manifest.json':rows.append({'path':f.relative_to(out).as_posix(),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
with (out/'remote_evidence_manifest.json').open('x') as f:json.dump({'files':rows,'files_count':len(rows),'bytes':sum(r['bytes'] for r in rows)},f,indent=2)
print(json.dumps({'postflight_process_check':record,'manifest_files':len(rows),'bytes':sum(r['bytes'] for r in rows)}))