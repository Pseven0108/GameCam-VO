"""Separate one-shot diagnostic permission; never upgrades formal SLAM admission."""
import hashlib,json,math,os,pathlib,re,time
from launch_authorization import LaunchContext,SCOPE
from runtime_dependency_pins import require,digest_file,RuntimePins
from diagnostic_phases import DIAGNOSTIC_TYPE,STOP_PHASE
SCHEMA='gamecam-bounded-diagnostic-candidate-v1'
DIAGNOSTIC_SCOPE=dict(SCOPE,permission_type=DIAGNOSTIC_TYPE,stop_after_phase=STOP_PHASE,
    frame_submission=False,tracker_run=False,ba=False,pose_evaluation=False)
def validate_diagnostic_authorization(c,sha,a,env,now=None):
    now=time.time() if now is None else now
    def check(ok,reason): require(ok,reason,'BLOCKED_BY_DIAGNOSTIC_AUTHORIZATION')
    check(a is not None,'NO_FRESH_DIAGNOSTIC_AUTHORIZATION')
    check(c.get('schema')==SCHEMA,'NOT_DIAGNOSTIC_CANDIDATE')
    check(c.get('diagnostic_admission_status')=='BOUNDED_DIAGNOSTIC_READY_WAITING_FOR_USER_AUTHORIZATION','DIAGNOSTIC_CANDIDATE_NOT_READY')
    check(c.get('entry_admission_status')=='DROIDW_ENTRY_PARTIAL_PASS','FORMAL_ADMISSION_MUST_REMAIN_PARTIAL')
    check(a.get('permission_type')==DIAGNOSTIC_TYPE,'WRONG_PERMISSION_TYPE')
    check(a.get('candidate_sha256')==sha,'DIAGNOSTIC_CANDIDATE_SHA_MISMATCH')
    check(c.get('diagnostic_scope')==DIAGNOSTIC_SCOPE and a.get('scope')==DIAGNOSTIC_SCOPE,'DIAGNOSTIC_SCOPE_MISMATCH')
    check(a.get('model_identity')==c.get('diagnostic_model_identity'),'DIAGNOSTIC_MODEL_IDENTITY_MISMATCH')
    check(a.get('gpu_uuid')==c.get('expected_gpu_uuid'),'DIAGNOSTIC_GPU_UUID_MISMATCH')
    check(a.get('session')==c.get('planned_session_id'),'DIAGNOSTIC_SESSION_MISMATCH')
    check(a.get('diagnostic_execution_authorized') is True and a.get('formal_120_frame_execution_authorized') is False,'DIAGNOSTIC_PERMISSION_FLAGS')
    check(type(a.get('attempt_limit')) is int and a['attempt_limit']==1 and c.get('maximum_authorizable_attempts')==1,'DIAGNOSTIC_ATTEMPT_LIMIT_NOT_ONE')
    check(a.get('automatic_retry') is False and c.get('automatic_retry') is False,'AUTOMATIC_RETRY_FORBIDDEN')
    check(a.get('consumed') is False,'DIAGNOSTIC_AUTHORIZATION_ALREADY_CONSUMED')
    check(isinstance(a.get('nonce'),str) and len(a['nonce'])>=32,'DIAGNOSTIC_NONCE_MISSING')
    for field in ('issued_unix','expires_unix'):
        check(type(a.get(field)) in (float,int) and math.isfinite(a[field]),'DIAGNOSTIC_TIME_INVALID')
    check(a['issued_unix']<=now<a['expires_unix'],'DIAGNOSTIC_AUTHORIZATION_EXPIRED')
    check(env.get('CUDA_VISIBLE_DEVICES')=='0','DIAGNOSTIC_GPU_SELECTION')
    check(a.get('gpu_environment_verified') is True and type(a.get('visible_device_count')) is int and a['visible_device_count']==1,'DIAGNOSTIC_GPU_NOT_VERIFIED')
    evidence=a.get('user_authorization_evidence',{})
    check(isinstance(evidence,dict) and isinstance(evidence.get('path'),str) and pathlib.Path(evidence['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',evidence.get('sha256','')) is not None,'USER_AUTHORIZATION_EVIDENCE_MISSING')
    return True

def verify_terminal_result(result,terminal,scope=DIAGNOSTIC_SCOPE):
    require(result.get('status')=='DIAGNOSTIC_STOP_COMPLETED' and result.get('error') is None,'DIAGNOSTIC_TERMINAL_NOT_SUCCESS')
    require(result.get('diagnostic_stop_phase')==scope['stop_after_phase'],'DIAGNOSTIC_TERMINAL_SCOPE_MISMATCH')
    require(result.get('frames_submitted')==0 and result.get('frames_completed')==0 and result.get('tracker_run_called') is False and result.get('BA_executed') is False,'DIAGNOSTIC_EXCEEDED_NO_FRAME_SCOPE')
    require(isinstance(result.get('diagnostic_loaded_weights'),list) and len(result['diagnostic_loaded_weights'])==4 and len(set(result['diagnostic_loaded_weights']))==4,'DIAGNOSTIC_WEIGHT_COVERAGE_INCOMPLETE')
    return True

class DiagnosticContext(LaunchContext):
    def validate_candidate(self):
        c=super().validate_candidate()
        require(c.get('schema')==SCHEMA and c.get('entry_admission_status')=='DROIDW_ENTRY_PARTIAL_PASS','DIAGNOSTIC_CANDIDATE_SCHEMA_OR_HISTORY')
        require(c.get('diagnostic_scope')==DIAGNOSTIC_SCOPE,'DIAGNOSTIC_SCOPE_DRIFT')
        require(c.get('GPU_execution_authorized') is False and c.get('current_attempt_limit')==0,'SEALED_CANDIDATE_MUST_BE_UNARMED')
        return c
    def validate_identity(self,c):
        from linux_safety import Nvml,EXPECTED_UUID,external_sample
        pins=RuntimePins(pathlib.Path(c['source_root'])/c['runtime_phase_relative']);r=pins.static_check()
        nvml=Nvml()
        try: gpu=external_sample(nvml,c['planned_session_id'],1)
        finally: nvml.close()
        require(gpu['gpu_uuid']==c['expected_gpu_uuid']==EXPECTED_UUID,'DIAGNOSTIC_LIVE_GPU_UUID_MISMATCH')
        require(not gpu['gpu_processes'],'UNKNOWN_GPU_COMPUTE_PROCESS')
        require(len(r['weights'])==4 and r['input_frames_verified'],'DIAGNOSTIC_ASSET_IDENTITY')
        return r
    def _auth(self,c,environment):
        require(self.authorization_path is not None,'NO_FRESH_DIAGNOSTIC_AUTHORIZATION')
        require(not self.authorization_path.is_symlink(),'DIAGNOSTIC_AUTHORIZATION_SYMLINK')
        a=json.loads(self.authorization_path.read_text())
        validate_diagnostic_authorization(c,self.candidate_sha,a,environment)
        e=a['user_authorization_evidence']; p=pathlib.Path(e['path'])
        require(p.is_file() and not p.is_symlink() and p.stat().st_size>0 and digest_file(p)==e['sha256'],'USER_AUTHORIZATION_EVIDENCE_SHA_MISMATCH')
        return a
    def validate(self,out,session,worker_command,monitor_command,environment,consume=False):
        require(self.authorization_path is not None,'NO_FRESH_DIAGNOSTIC_AUTHORIZATION')
        c=self.validate_candidate(); a=self._auth(c,environment)
        require(str(pathlib.Path(out).resolve())==c['planned_session_directory'] and session==c['planned_session_id'],'DIAGNOSTIC_OUTPUT_SESSION_MISMATCH')
        expected_worker=c['worker_command_prefix']+['--candidate',str(self.candidate_path),'--candidate-sha',self.candidate_sha,'--authorization',str(self.authorization_path),'--session-dir',str(out),'--session',session]
        require(worker_command==expected_worker and monitor_command==c['monitor_command_prefix']+['--monitor',str(out),'--session',session],'DIAGNOSTIC_COMMAND_DRIFT')
        for k,v in c['pinned_environment'].items():require(environment.get(k)==v,'DIAGNOSTIC_ENVIRONMENT_DRIFT:'+k)
        from ipc_runtime import expected_root
        require(c['planned_ipc_root']==str(expected_root(session)),'DIAGNOSTIC_IPC_SESSION_MISMATCH')
        ledger=pathlib.Path(c['planned_authorization_ledger']); nonce_root=pathlib.Path(c['nonce_registry_root'])
        nonce=nonce_root/(hashlib.sha256(a['nonce'].encode()).hexdigest()+'.json')
        require(not ledger.exists() and not ledger.is_symlink() and not nonce.exists() and not nonce.is_symlink(),'DIAGNOSTIC_PERMISSION_ALREADY_CONSUMED')
        self.validate_identity(c)
        if consume:
            require(pathlib.Path(out).is_dir() and not self.claimed,'DIAGNOSTIC_CLAIM_STATE')
            nonce_root.mkdir(parents=True,exist_ok=True,mode=0o700)
            require(nonce_root.resolve()==nonce_root and not nonce_root.is_symlink(),'DIAGNOSTIC_NONCE_ROOT_ESCAPE')
            payload=dict(permission_type=DIAGNOSTIC_TYPE,candidate_sha256=self.candidate_sha,session=session,nonce=a['nonce'],attempts=1,claimed_unix=time.time(),supervisor_pid=os.getpid())
            for p in (nonce,ledger):
                fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'w') as f:json.dump(payload,f);f.flush();os.fsync(f.fileno())
            self.claimed=True
        return True
    def validate_child(self,session_dir,session):
        c=self.validate_candidate();a=self._auth(c,os.environ)
        require(str(pathlib.Path(session_dir).resolve())==c['planned_session_directory'] and session==c['planned_session_id'],'DIAGNOSTIC_CHILD_SESSION')
        require(os.getppid()==int(os.environ['GAMECAM_SUPERVISOR_PID']),'DIAGNOSTIC_CHILD_PARENT')
        ledger=json.loads(pathlib.Path(c['planned_authorization_ledger']).read_text())
        require(ledger.get('permission_type')==DIAGNOSTIC_TYPE and ledger.get('candidate_sha256')==self.candidate_sha and ledger.get('session')==session and ledger.get('nonce')==a['nonce'] and ledger.get('attempts')==1 and ledger.get('supervisor_pid')==os.getppid(),'DIAGNOSTIC_CHILD_CLAIM_MISMATCH')
        p=pathlib.Path(session_dir)/'diagnostic_child_claim.json'
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(dict(pid=os.getpid(),session=session,candidate_sha256=self.candidate_sha),f)
        return c
    def validate_terminal(self,out,terminal):
        result=json.loads((pathlib.Path(out)/'model/result.json').read_text())
        verify_terminal_result(result,terminal,self._candidate['diagnostic_scope'])
