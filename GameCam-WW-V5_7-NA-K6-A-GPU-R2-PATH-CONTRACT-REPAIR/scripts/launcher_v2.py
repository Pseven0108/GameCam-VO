"""One-shot V2 launch entry. Missing fresh authorization rejects before any subprocess."""
import argparse,json,os,pathlib,sys
from launch_authorization import LaunchContext
from runner_core import supervise_once

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--candidate-sha',required=True);p.add_argument('--authorization');p.add_argument('--session',required=True);a=p.parse_args(argv)
    context=LaunchContext(a.candidate,a.candidate_sha,a.authorization)
    try:
        # Refuse unarmed requests before candidate IO, output creation, monitoring or model imports.
        if not a.authorization:raise RuntimeError('NO_FRESH_GPU_AUTHORIZATION')
        c=context.validate_candidate();out=c['planned_session_directory']
        worker=c['worker_command_prefix']+['--candidate',str(context.candidate_path),'--candidate-sha',a.candidate_sha,'--authorization',str(context.authorization_path),'--session-dir',out,'--session',a.session]
        monitor=c['monitor_command_prefix']+['--monitor',out,'--session',a.session]
        env=dict(os.environ,**c['pinned_environment']);env['GAMECAM_SUPERVISOR_PID']=str(os.getpid());env['GAMECAM_RUN_SESSION_DIR']=out
        result=supervise_once(out,a.session,worker,monitor,'droidw',env=env,expected_frames=120,launch_context=context)
        print(json.dumps(result),flush=True);return 0 if result['passed'] else 2
    except BaseException as e:
        print(json.dumps({'status':'MODEL_EXECUTION_NOT_AUTHORIZED_OR_PRELAUNCH_BLOCKED','reason':str(e),'torch_imported':'torch' in sys.modules,'worker_spawned':False if not context.claimed else 'UNKNOWN_CHECK_SUPERVISOR_LOG','new_attempts':1 if context.claimed else 0,'gpu_authorization_generated':False}),flush=True);return 3
if __name__=='__main__':raise SystemExit(main())
