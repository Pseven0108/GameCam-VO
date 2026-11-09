"""Preparation never arms this entry. A new external user permission is mandatory."""
import argparse,json,os,sys
from diagnostic_authorization import DiagnosticContext
from runner_core import supervise_once

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--candidate-sha',required=True);p.add_argument('--authorization');p.add_argument('--session',required=True);a=p.parse_args(argv)
    ctx=DiagnosticContext(a.candidate,a.candidate_sha,a.authorization)
    try:
        if not a.authorization:raise RuntimeError('NO_FRESH_DIAGNOSTIC_AUTHORIZATION')
        c=ctx.validate_candidate();out=c['planned_session_directory']
        worker=c['worker_command_prefix']+['--candidate',str(ctx.candidate_path),'--candidate-sha',a.candidate_sha,'--authorization',str(ctx.authorization_path),'--session-dir',out,'--session',a.session]
        monitor=c['monitor_command_prefix']+['--monitor',out,'--session',a.session]
        env=dict(os.environ,**c['pinned_environment']);env['GAMECAM_SUPERVISOR_PID']=str(os.getpid());env['GAMECAM_RUN_SESSION_DIR']=out
        r=supervise_once(out,a.session,worker,monitor,'droidw_diagnostic',env=env,expected_frames=0,launch_context=ctx)
        print(json.dumps(r),flush=True);return 0 if r['passed'] else 2
    except BaseException as e:
        print(json.dumps(dict(status='DIAGNOSTIC_NOT_AUTHORIZED_OR_PRELAUNCH_BLOCKED',reason=str(e),torch_imported='torch' in sys.modules,worker_spawned=False if not ctx.claimed else 'SEE_SUPERVISOR_LOG',new_attempts=1 if ctx.claimed else 0)),flush=True);return 3
if __name__=='__main__':raise SystemExit(main())
