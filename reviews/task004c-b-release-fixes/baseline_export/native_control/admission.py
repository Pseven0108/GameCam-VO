"""Stdlib-only pre-model admission. No CUDA context, framework or model import."""
import hashlib,json,os,pathlib,shutil,subprocess,time

GIB=1024**3
MODES=('capture','restore_check','record_S1','record_S0','replay_D0_S1','replay_D1_S0')
COUNTS={'capture':1,'restore_check':1,'record_S1':1,'record_S0':1,'replay_D0_S1':1,'replay_D1_S0':1}

def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def command(args):
    try:
        q=subprocess.run(args,capture_output=True,text=True,timeout=20)
        return {'args':args,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
    except Exception as e:return {'args':args,'exit_code':None,'error':repr(e)}

def preflight(root,lock,*,cpu_report):
    root=pathlib.Path(root);issues=[]
    report=json.loads(pathlib.Path(cpu_report).read_text())
    if report['total']!=report['passed'] or report['failures'] or report['errors'] or report.get('cuda_initialized'):
        issues.append('CPU_PHASE_NOT_PASSED')
    pins={**lock['remote_pins'],**lock['execution_source_pins']};verified={}
    for p,pin in pins.items():
        value=sha(p) if pathlib.Path(p).is_file() else None;verified[p]={'actual':value,'expected':pin,'match':value==pin}
    if not all(x['match'] for x in verified.values()):issues.append('IDENTITY_CHANGED')
    nvidia=command(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'])
    apps=command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits']) if nvidia['exit_code']==0 else None
    if nvidia['exit_code']!=0:issues.append('GPU_STATUS_UNVERIFIED_TOOL_FAILED')
    else:
        rows=[x.strip() for x in nvidia['stdout'].splitlines() if x.strip()]
        if len(rows)!=1 or 'RTX 3090' not in rows[0]:issues.append('REQUIRED_SINGLE_RTX3090_NOT_CONFIRMED')
        elif float(rows[0].split(',')[2])<23000:issues.append('GPU_FREE_MEMORY_BELOW_FROZEN_ADMISSION')
        if apps is None or apps['exit_code']!=0 or apps['stdout'].strip():issues.append('GPU_COMPUTE_OCCUPIED_OR_UNKNOWN')
    disk=dict(zip(('total','used','free'),shutil.disk_usage(root)))
    shm=dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm')))
    # Native spawn exports the full CPU image store as well as explicit DINO
    # shared memory. This is a scoped byte budget, not the withdrawn 8GiB rule.
    shared_candidate=500*3*360*640*4 + 500*25*45*384*4
    if shm['free']<shared_candidate:issues.append('SHM_BELOW_FULL_NATIVE_SPAWN_STORAGE_CANDIDATE')
    # Static minimum excludes correlations and models; the live closure gate
    # computes the exact complete storage budget before writing one real C0.
    if disk['free']<10*GIB+7468230540+512*1024**2:issues.append('DATA_DISK_BELOW_C0_MINIMUM_AND_SAFETY_FLOOR')
    result={'time_unix':time.time(),'issues':issues,'admitted':not issues,'models_imported':False,'cuda_context_initialized':False,
        'gpu':nvidia,'compute_apps':apps,'data_disk':disk,'shared_memory':shm,'shared_storage_candidate_bytes':shared_candidate,
        'complete_C0_bytes':None,'C0_exact_live_inventory_still_required':True,'protected_pins':verified,
        'native_C0_captured':False,'formal_B_runs_authorized':False,'max_rgb':80,'retry_allowed':False}
    return result

def validate_mode(mode,max_rgb):
    if mode not in MODES or type(max_rgb) is not int or max_rgb!=80:
        raise ValueError('Only named, single bounded native validation modes ending at RGB080 are authorized')
    return True
