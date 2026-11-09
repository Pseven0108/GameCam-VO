"""Pre-spawn authorization boundary. This module never queries a GPU or creates a permit."""
import hashlib,json,os,pathlib,subprocess,time
from runtime_dependency_pins import PinError,digest_file,require

SCOPE={'method':'droidw','case':'V56_01_middle','max_frames':120,'stride':1,'buffer':350,'warmup':12,'motion_filter':3.0,'mapping':False}

def validate_authorization(candidate, candidate_sha, authorization, environment, now=None):
    """Pure checks; test authorizations are in-memory fixtures, never GPU permit files."""
    now=time.time() if now is None else now
    require(authorization is not None,'NO_FRESH_GPU_AUTHORIZATION','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization.get('candidate_sha256')==candidate_sha,'CANDIDATE_SHA_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(candidate.get('scope')==SCOPE and authorization.get('scope')==SCOPE,'UNAUTHORIZED_WORKER_OR_SCOPE','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization.get('model_execution_authorized') is True,'WORKER_NOT_AUTHORIZED','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(type(authorization.get('attempt_limit')) is int and authorization['attempt_limit']==1,'ATTEMPT_LIMIT_NOT_ONE','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization.get('automatic_retry') is False,'AUTOMATIC_RETRY_FORBIDDEN','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization.get('consumed') is False,'AUTHORIZATION_ALREADY_CONSUMED','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(isinstance(authorization.get('nonce'),str) and len(authorization['nonce'])>=16,'AUTHORIZATION_NONCE_MISSING','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(type(authorization.get('issued_unix')) in (float,int) and type(authorization.get('expires_unix')) in (float,int),'AUTHORIZATION_TIME_MISSING','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization['issued_unix']<=now<authorization['expires_unix'],'AUTHORIZATION_EXPIRED_OR_NOT_YET_VALID','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(authorization.get('gpu_environment_verified') is True and type(authorization.get('visible_device_count')) is int and authorization.get('visible_device_count')==1,'GPU_ENVIRONMENT_NOT_VERIFIED','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(environment.get('CUDA_VISIBLE_DEVICES') in ('0',None),'GPU_INVISIBLE_OR_INVALID_DEVICE_SELECTION','BLOCKED_BY_AUTHORIZATION_GUARD')
    require(candidate.get('maximum_authorizable_attempts')==1 and candidate.get('automatic_retry') is False,'CANDIDATE_ATTEMPT_POLICY','BLOCKED_BY_AUTHORIZATION_GUARD')
    return True

class LaunchContext:
    def __init__(self,candidate_path,candidate_sha,authorization_path):
        self.candidate_path=pathlib.Path(candidate_path).resolve();self.candidate_sha=candidate_sha
        self.authorization_path=pathlib.Path(authorization_path).resolve() if authorization_path else None
        self.claimed=False;self._candidate=None

    def validate_candidate(self):
        require(digest_file(self.candidate_path)==self.candidate_sha,'CANDIDATE_SHA_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        c=json.loads(self.candidate_path.read_text(encoding='utf-8-sig'))
        root=pathlib.Path(c['source_root']).resolve(strict=True)
        git=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True)
        require(git.stdout.strip()==c['source_git_commit'],'SOURCE_COMMIT_DRIFT','BLOCKED_BY_AUTHORIZATION_GUARD')
        status=subprocess.run(['git','status','--porcelain','--untracked-files=all'],cwd=root,capture_output=True,text=True,check=True)
        require(not status.stdout,'CANDIDATE_SOURCE_NOT_CLEAN','BLOCKED_BY_AUTHORIZATION_GUARD')
        for record in c['source_records']:
            rel=pathlib.PurePosixPath(record['path']);require(not rel.is_absolute() and '..' not in rel.parts,'SOURCE_PATH_ESCAPE','BLOCKED_BY_AUTHORIZATION_GUARD')
            p=root.joinpath(*rel.parts)
            require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root),'SOURCE_FILE_TYPE_DRIFT','BLOCKED_BY_AUTHORIZATION_GUARD')
            require(digest_file(p)==record['sha256'],'SOURCE_SHA_DRIFT:'+str(rel),'BLOCKED_BY_AUTHORIZATION_GUARD')
        for record in c.get('external_source_records',[]):
            p=pathlib.Path(record['path']);require(p.is_file() and digest_file(p)==record['sha256'],'EXTERNAL_SOURCE_SHA_DRIFT:'+str(p),'BLOCKED_BY_AUTHORIZATION_GUARD')
        for record in c['configuration_records']:
            p=pathlib.Path(record['path']);require(p.is_file() and digest_file(p)==record['sha256'],'CONFIGURATION_IDENTITY_DRIFT','BLOCKED_BY_AUTHORIZATION_GUARD')
        self._candidate=c;return c

    def validate(self,out,session,worker_command,monitor_command,environment,consume=False):
        # No authorization means no file reads, directories, monitor or worker processes.
        require(self.authorization_path is not None,'NO_FRESH_GPU_AUTHORIZATION','BLOCKED_BY_AUTHORIZATION_GUARD')
        c=self.validate_candidate();a=json.loads(self.authorization_path.read_text(encoding='utf-8-sig'))
        validate_authorization(c,self.candidate_sha,a,environment or os.environ)
        out=pathlib.Path(out).resolve()
        require(str(out)==c['planned_session_directory'] and session==a.get('session'),'OUTPUT_OR_SESSION_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        require(worker_command==c['worker_command_prefix']+['--candidate',str(self.candidate_path),'--candidate-sha',self.candidate_sha,'--authorization',str(self.authorization_path),'--session-dir',str(out),'--session',session],'WORKER_COMMAND_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        require(monitor_command==c['monitor_command_prefix']+['--monitor',str(out),'--session',session],'MONITOR_COMMAND_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        ledger=pathlib.Path(c['planned_authorization_ledger'])
        require(not ledger.exists() and not ledger.is_symlink(),'AUTHORIZATION_ALREADY_CONSUMED','BLOCKED_BY_AUTHORIZATION_GUARD')
        if consume:
            require(out.is_dir() and not self.claimed,'ATTEMPT_STATE_INVALID','BLOCKED_BY_AUTHORIZATION_GUARD')
            # This exclusive claim is reachable only after a separately supplied fresh user authorization.
            ledger.parent.mkdir(parents=True,exist_ok=True)
            with ledger.open('x',encoding='utf-8') as f:json.dump({'candidate_sha256':self.candidate_sha,'nonce':a['nonce'],'session':session,'claimed_unix':time.time(),'attempts':1},f)
            self.claimed=True
        return True

    def validate_child(self,session_dir,session):
        require(self.authorization_path is not None,'NO_FRESH_GPU_AUTHORIZATION','BLOCKED_BY_AUTHORIZATION_GUARD')
        c=self.validate_candidate();a=json.loads(self.authorization_path.read_text(encoding='utf-8-sig'))
        validate_authorization(c,self.candidate_sha,a,os.environ)
        require(str(pathlib.Path(session_dir).resolve())==c['planned_session_directory'] and session==a.get('session'),'CHILD_SESSION_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        ledger=json.loads(pathlib.Path(c['planned_authorization_ledger']).read_text())
        require(ledger['candidate_sha256']==self.candidate_sha and ledger['session']==session and ledger['nonce']==a['nonce'] and ledger['attempts']==1,'CHILD_ONE_SHOT_CLAIM_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
        return c
