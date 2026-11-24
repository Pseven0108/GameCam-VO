import json
from remote_cpu import ROOT,call
code=r'''
import pathlib,json,hashlib,subprocess,os,shutil,stat,datetime
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1');s=r/'source_candidate'
state=json.loads((r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').read_text())
assert state['budgets']['CPU_correction_rounds_used']==2 and state['budgets']['new_GPU_C0_lifecycles_used']==0
result=json.loads((r/'evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION_RECEIPT.json').read_text())
assert result['exit_code']==1 and 'ConfigDict' in result['stderr_tail']
assert not (r/'C0').exists() and not list((r/'attempts').iterdir())
status=subprocess.check_output(['git','-C',str(s),'status','--porcelain'],text=True)
assert {row[3:] for row in status.splitlines()}=={'native_control/snapshot.py','native_control/metric3d_identity.py'},status
subprocess.run(['git','-C',str(s),'add','--','native_control/snapshot.py','native_control/metric3d_identity.py'],check=True,capture_output=True)
q=subprocess.run(['git','-C',str(s),'commit','-m','Audit source-pinned LoRA identities and lossless checkpoint archives; restore blocked on ConfigDict'],capture_output=True,text=True)
if q.returncode:raise RuntimeError(q.stderr)
head=subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD^{tree}'],text=True).strip()
patch=subprocess.check_output(['git','-C',str(s),'diff','02f8c8308274489ff7eff83fa9b87b98db74122e',head,'--binary'])
(r/'evidence/AUTONOMOUS_CANDIDATE_SOURCE.patch').write_bytes(patch)
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
source={'source_commit':head,'source_tree':tree,'parent_commit':'02f8c8308274489ff7eff83fa9b87b98db74122e','changed_files':subprocess.check_output(['git','-C',str(s),'diff','HEAD^','HEAD','--name-only'],text=True).splitlines(),'BA_math_changed':False,'model_forward_sources_changed':False,'CUDA_extension_rebuilt':False,'patch_sha256':sha(r/'evidence/AUTONOMOUS_CANDIDATE_SOURCE.patch')}
(r/'evidence/AUTONOMOUS_SOURCE_PROVENANCE.json').write_text(json.dumps(source,indent=2))
# Reclaim only this task's terminated diagnostic Arena; all old failed files stay.
a=r/'cpu_tests/complete_object_diagnostic_r1_fixture16/shared_cpu';assert a.resolve().is_relative_to(r.resolve()) and not a.is_symlink()
files=list(a.glob('*.bin'));assert len(files)==2
paths={str(p.resolve()) for p in files};active=[];errors=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if any(p in (proc/'maps').read_text() for p in paths):active.append(proc.name)
  for fd in (proc/'fd').iterdir():
   try:
    if os.readlink(fd).removesuffix(' (deleted)') in paths:active.append(proc.name)
   except FileNotFoundError:pass
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:errors.append(proc.name)
assert not active and not errors,(active,errors)
rows=[]
for p in files:
 z=p.stat();assert p.name==str(z.st_ino)+'.bin' and z.st_size in (1382400000,864000000) and stat.S_IMODE(z.st_mode)==0o600
 rows.append({'path':str(p),'sha256':sha(p),'bytes':z.st_size,'ino':z.st_ino,'dev':z.st_dev})
cleanup={'scope':'NEW_TASK_CPU_DIAGNOSTIC_FIXTURE16_ONLY','files':rows,'active_maps_or_fds':active,'permission_errors':errors,'historical_Arena_removed':False,'disk_free_before':shutil.disk_usage(r).free}
(r/'evidence/FINAL_CPU_ARENA_CLEANUP_INTENT.json').write_text(json.dumps(cleanup,indent=2))
for row in rows:
 p=pathlib.Path(row['path']);z=p.stat();assert (z.st_ino,z.st_dev,z.st_size)==(row['ino'],row['dev'],row['bytes']);p.unlink()
cleanup['disk_free_after']=shutil.disk_usage(r).free
(r/'evidence/FINAL_CPU_ARENA_CLEANUP_RECEIPT.json').write_text(json.dumps(cleanup,indent=2))
# Permanently preserve the failed real-model CPU snapshot, including all weights,
# only on this private data disk; never publish its tensor payloads to GitHub.
partial=json.loads((r/'cpu_tests/closure_roundtrip_r2_rng_validation/PARTIAL_REPORT.json').read_text())
origin=pathlib.Path(partial['CPU_snapshot_path']);dest=r/'cpu_tests/closure_roundtrip_r2_rng_validation/snapshot_evidence'
size=sum(p.stat().st_size for p in origin.iterdir() if p.is_file())
assert shutil.disk_usage(r).free>=10*1024**3+size+512*1024**2 and not dest.exists()
shutil.copytree(origin,dest)
matches={p.name:{'bytes':p.stat().st_size,'sha256':sha(p),'copy_sha256':sha(dest/p.name)} for p in origin.iterdir() if p.is_file()}
assert all(x['sha256']==x['copy_sha256'] for x in matches.values())
preserve={'kind':'CPU_REAL_WEIGHTED_MODEL_FIXTURE_NOT_C0','source':str(origin),'private_data_disk_copy':str(dest),'bytes':size,'files_verified':len(matches),'SHA_matches':True,'ConfigDict_restore_passed':False,'contains_model_weights_do_not_publish':True,'files':matches}
(r/'evidence/CPU_FAILED_SNAPSHOT_PRESERVATION.json').write_text(json.dumps(preserve,indent=2))
old=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1/attempts/capture/shared_cpu')
old_rows=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'ino':p.stat().st_ino} for p in sorted(old.glob('*.bin'))]
assert len(old_rows)==2 and sum(v['bytes'] for v in old_rows)==2246400000
(r/'evidence/HISTORICAL_FAILED_ARENAS_FINAL_PRESERVATION.json').write_text(json.dumps({'retained':True,'files':old_rows},indent=2))
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
state.update(status='BLOCKED',phase='A',stop_reason='CPU_RESTORE_CONFIGDICT_UNSUPPORTED_AND_TWO_CORRECTION_ROUNDS_EXHAUSTED',next_action='Review source-pinned ConfigDict mapping-content and construction-free restore adapter requirements; no GPU launch without a newly approved closure correction budget')
state['phases']['A'].update(status='BLOCKED',source_commit=head,source_SHA=tree,configuration_SHA='a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc',input_manifest_SHA='5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537',end_time=now,stop_reason=state['stop_reason'],outputs=['evidence/CPU_CORRECTION_ROUND2.json','evidence/CPU_LEGACY152_R2_RECEIPT.json','evidence/CPU_ROUNDTRIP_R2_RNG_VALIDATION_RECEIPT.json','evidence/CONFIGDICT_BLOCKER_DIAGNOSTIC.json','evidence/CPU_FAILED_SNAPSHOT_PRESERVATION.json'])
state['phases']['A']['artifacts_SHA256']={p:sha(r/p) for p in state['phases']['A']['outputs']}
state['phases']['B'].update(status='PARTIAL_RESOURCE_AUDIT_ONLY_NO_REAL_C0_BUDGET',end_time=now,outputs=['evidence/PHASE_B_RESOURCE_AND_ASSET_PREFLIGHT.json'],stop_reason='A blocked; real initialized C0 does not exist')
for k in 'CDEFG':state['phases'][k].update(status='NOT_EXECUTED_DEPENDENCY_BLOCKED',stop_reason=state['stop_reason'])
state['finished_at']=now
(r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(state,indent=2))
with (r/'TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md').open('a') as f:
 f.write('\n'+now+' — Stopped before GPU: CPU roundtrip hit ConfigDict mapping/constructor blocker after correction round2. Historical152 pass. New GPU C0=0/2; no restore, schedule, or formal GPU arms. Original data preserved. GPU allocation remains online.\n')
print(json.dumps({'state':state,'source':source,'CPU_snapshot_preserved_bytes':size,'CPU_snapshot_file_count':len(matches),'disk':shutil.disk_usage(r)._asdict(),'GPU':subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,memory.free','--format=csv,noheader'],capture_output=True,text=True).stdout.strip(),'GPU_processes':subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()}))
'''
d=json.loads(call('FINALIZE_TRUE_CPU_BLOCKER_AND_PRESERVE',code,timeout=300))
(ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(d['state'],indent=2))
(ROOT/'evidence/FINAL_REMOTE_STATE.json').write_text(json.dumps(d,indent=2))
print(json.dumps({k:v for k,v in d.items() if k!='state'},indent=2))
