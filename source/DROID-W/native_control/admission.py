"""Stdlib-only pre-model admission. No CUDA context, framework or model import."""
import hashlib,importlib.metadata,json,os,pathlib,shutil,subprocess,time

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

def cpu_storage_admission(root,*,backend='native_shm',validation=None):
    root=pathlib.Path(root);issues=[];candidate_bytes=2246400000
    result={'backend':backend,'native_large_CPU_storage_bytes':candidate_bytes,'extra_data_disk_reservation_bytes':0,
            'required_shm_bytes':candidate_bytes,'validation_passed':False,'issues':issues}
    if backend=='native_shm':return result
    if backend!='owned_file_mmap':
        issues.append('UNKNOWN_CPU_STORAGE_BACKEND');return result
    result['required_shm_bytes']=64*1024**2
    result['extra_data_disk_reservation_bytes']=candidate_bytes+16*1024**2
    # 64MiB is an explicit residual IPC envelope, not a measured native minimum.
    result['residual_shm_is_static_envelope_not_native_measurement']=True
    if validation is None or not pathlib.Path(validation).is_file():
        issues.append('FILE_BACKED_CPU_VALIDATION_MISSING');return result
    doc=json.loads(pathlib.Path(validation).read_text())
    if not (doc.get('PASS') is True and doc.get('total_tensor_bytes')==candidate_bytes
            and doc.get('shm_delta_bytes',candidate_bytes)<1024**2
            and doc.get('file_backed_module_sha256')==sha(root/'native_control/file_backed.py')
            and doc.get('torch_distribution_version')==importlib.metadata.version('torch')):
        issues.append('FILE_BACKED_CPU_VALIDATION_MISMATCH');return result
    result['validation_passed']=True
    result['native_Tracker_Rerun_GPU_validation_passed']=False
    return result

def preflight(root,lock,*,cpu_report,cpu_storage_backend='native_shm',storage_validation=None):
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
    storage=cpu_storage_admission(root,backend=cpu_storage_backend,validation=storage_validation);issues.extend(storage['issues'])
    if shm['free']<storage['required_shm_bytes']:issues.append('SHM_BELOW_SELECTED_BACKEND_RESERVATION')
    # Static minimum excludes correlations and models; the live closure gate
    # computes the exact complete storage budget before writing one real C0.
    if disk['free']<10*GIB+7468230540+512*1024**2+storage['extra_data_disk_reservation_bytes']:issues.append('DATA_DISK_BELOW_C0_MINIMUM_AND_SAFETY_FLOOR')
    result={'time_unix':time.time(),'issues':issues,'admitted':not issues,'models_imported':False,'cuda_context_initialized':False,
        'gpu':nvidia,'compute_apps':apps,'data_disk':disk,'shared_memory':shm,'shared_storage_candidate_bytes':shared_candidate,'cpu_storage_admission':storage,
        'complete_C0_bytes':None,'C0_exact_live_inventory_still_required':True,'protected_pins':verified,
        'native_C0_captured':False,'formal_B_runs_authorized':False,'max_rgb':80,'retry_allowed':False}
    return result

def validate_mode(mode,max_rgb):
    if mode not in MODES or type(max_rgb) is not int or max_rgb!=80:
        raise ValueError('Only named, single bounded native validation modes ending at RGB080 are authorized')
    return True


def continuation_preflight(root,release):
    """Same frozen identity/GPU gate, with restoration rather than C0 reservation."""
    root=pathlib.Path(root);issues=[]
    pins={**release['protected_pins'],**release['runtime_pins']}
    checked={p:{'actual':sha(p) if pathlib.Path(p).is_file() else None,'expected':v} for p,v in pins.items()}
    if any(v['actual']!=v['expected'] for v in checked.values()):issues.append('IDENTITY_CHANGED')
    gpu=command(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'])
    apps=command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'])
    rows=gpu.get('stdout','').strip().splitlines()
    if gpu['exit_code']!=0 or len(rows)!=1 or 'RTX 3090' not in rows[0]:issues.append('REQUIRED_SINGLE_RTX3090_NOT_CONFIRMED')
    elif float(rows[0].split(',')[2])<23000:issues.append('GPU_FREE_MEMORY_BELOW_FROZEN_ADMISSION')
    if apps['exit_code']!=0 or apps['stdout'].strip():issues.append('GPU_COMPUTE_OCCUPIED_OR_UNKNOWN')
    disk=dict(zip(('total','used','free'),shutil.disk_usage(root)))
    reservation=2246400000+1024**3
    if disk['free']<10*GIB+reservation:issues.append('DATA_DISK_BELOW_RESTORE_ARENA_LOGS_AND_FLOOR')
    shm=dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm')))
    if shm['free']<64*1024**2:issues.append('SHM_BELOW_RESIDUAL_IPC_ENVELOPE')
    return {'admitted':not issues,'issues':issues,'gpu':gpu,'compute_apps':apps,'protected_pins':checked,
            'data_disk':disk,'shared_memory':shm,'restore_reservation_bytes':reservation,
            'models_imported':False,'cuda_context_initialized':False}
