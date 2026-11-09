"""Failure-only terminal publication for the authorized child's pre-model stages."""
import json, pathlib, time, traceback
from linux_safety import atomic_json
from worker_terminal import publish_terminal

def publish_pre_model_failure(result, output, session_dir, session, exc,
                              phase, boundary=None, policy=None, diagnostic=None):
    primary = str(exc) or type(exc).__name__
    # This helper is called while handling the original exception. Save its traceback first.
    try:
        original_traceback = traceback.format_exc()
    except BaseException as formatting_error:
        frames = []
        tb = exc.__traceback__
        while tb is not None:
            frames.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name})
            tb = tb.tb_next
        original_traceback = json.dumps({'exception_type':type(exc).__name__,'error':primary,'frames':frames,'formatting_error':str(formatting_error)})
    result.update(status='BLOCKED_BY_MODEL_IO_BOUNDARY' if primary.startswith('MODEL_')
                  else 'BLOCKED_BY_DEPENDENCY_IMPORT', error=primary,
                  primary_exception_type=type(exc).__name__, traceback=original_traceback,
                  failure_phase=phase, early_failure=True,
                  frames_submitted=0, frames_completed=0,
                  tracker_run_called=False, BA_executed=False,
                  diagnostic_loaded_weights=[], stopped_unix=time.time())
    result['io_boundary_denied_events'] = list(boundary.events) if boundary else []
    result['ipc_events'] = list(policy.events) if policy else []
    result['phase_error_reporting_failures'] = list(getattr(diagnostic,'error_reporting_failures',[]))
    # Do not attempt CUDA telemetry while processing a pre-model failure.
    out = pathlib.Path(output); root = pathlib.Path(session_dir).absolute()
    if out.absolute() != root / 'model' or out.resolve() != out.absolute() or out.is_symlink():
        raise RuntimeError('EARLY_FAILURE_OUTPUT_IDENTITY') from exc
    out.mkdir(mode=0o700, exist_ok=True)
    if (out / 'result.json').exists():
        raise RuntimeError('EARLY_FAILURE_RESULT_ALREADY_EXISTS') from exc
    atomic_json(out / 'result.json', result)
    return publish_terminal(root, session, out / 'result.json', 'droidw_diagnostic')
