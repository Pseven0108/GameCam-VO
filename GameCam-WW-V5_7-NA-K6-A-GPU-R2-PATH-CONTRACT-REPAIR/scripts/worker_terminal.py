"""Atomic native worker termination handoff, separate from CUDA running-state freshness."""
import hashlib,json,math,os,pathlib,time
from linux_safety import atomic_json,SafetyStop
TERMINAL_SCHEMA='gamecam-worker-terminal-v1'
TERMINAL_CLEANUP_SECONDS=5.0

def publish_terminal(session_dir,session,result_path,execution_kind):
    d=pathlib.Path(session_dir);p=pathlib.Path(result_path);raw=p.read_bytes();r=json.loads(raw)
    if r.get('status') in (None,'RUNNING'):raise SafetyStop('TERMINAL_RESULT_NOT_FINAL')
    payload={'schema':TERMINAL_SCHEMA,'session':session,'worker_pid':os.getpid(),'execution_kind':execution_kind,'result_relative_path':str(p.relative_to(d)),'result_sha256':hashlib.sha256(raw).hexdigest(),'status':r['status'],'primary_failure':r.get('error'),'frames_submitted':r.get('frames_submitted',0),'frames_completed':r.get('frames_completed',0),'monotonic_time':time.monotonic(),'unix_time':time.time(),'model_work_finished':True}
    target=d/'worker_terminal.json'
    if target.exists():raise SafetyStop('TERMINAL_ALREADY_PUBLISHED')
    atomic_json(target,payload);return payload

def read_terminal(out,session,pid,kind):
    p=pathlib.Path(out)/'worker_terminal.json'
    if p.is_symlink():raise SafetyStop('INVALID_WORKER_TERMINAL:terminal symlink')
    if not p.exists():return None
    try:
        t=json.loads(p.read_text());rpath=pathlib.PurePosixPath(t['result_relative_path'])
        if t.get('schema')!=TERMINAL_SCHEMA or t.get('session')!=session or t.get('worker_pid')!=pid or t.get('execution_kind')!=kind or t.get('model_work_finished') is not True:raise ValueError('identity')
        expected='model/result.json' if kind=='droidw' else 'fake_result.json'
        if str(rpath)!=expected or rpath.is_absolute() or '..' in rpath.parts:raise ValueError('path')
        result_path=pathlib.Path(out)/str(rpath)
        if result_path.is_symlink() or result_path.resolve()!=result_path.absolute():raise ValueError('symlink')
        raw=result_path.read_bytes();r=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=t['result_sha256'] or r.get('status') in (None,'RUNNING') or r['status']!=t['status'] or r.get('error')!=t.get('primary_failure'):raise ValueError('result binding')
        if not isinstance(t.get('status'),str) or (t['status']=='RUN_COMPLETED')!=(t.get('primary_failure') is None):raise ValueError('terminal status')
        if t.get('primary_failure') is not None and (not isinstance(t['primary_failure'],str) or not t['primary_failure']):raise ValueError('terminal error')
        for key in ['frames_submitted','frames_completed']:
            if type(t.get(key)) is not int or type(r.get(key,0)) is not int or t[key]<0 or t[key]>120 or t[key]!=r.get(key,0):raise ValueError('frames')
        if t['frames_completed']>t['frames_submitted']:raise ValueError('frame order')
        for key,now in [('monotonic_time',time.monotonic()),('unix_time',time.time())]:
            value=t.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or value<=0 or value>now+1:raise ValueError('time')
        return t
    except (OSError,ValueError,TypeError,KeyError) as exc:raise SafetyStop('INVALID_WORKER_TERMINAL:'+str(exc)) from exc
