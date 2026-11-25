"""Resume orchestration only; completed GPU attempts are never restarted."""
import os, sys, json, time, pathlib, traceback, tarfile, io
import numpy as np
import continue_serial as c

ROOT = c.ROOT
LOCK = ROOT / '04_results/SUPERVISOR_RESUME02.lock'

def health(state):
    artifact = c.RECEIVER / ('result_' + state + '.tar')
    rows = []
    with tarfile.open(artifact, 'r:') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if name not in [u+'_'+v+'.npz' for u in ('FROZEN','NATIVE_UPDATE') for v in 'ABCD']:
                continue
            with np.load(io.BytesIO(archive.extractfile(member).read()), allow_pickle=False) as data:
                for iteration in (1,2):
                    prefix = 'iter%d_' % iteration
                    raw = data[prefix+'L_damped_raw'].astype(np.float64)
                    matrix = np.tril(raw) + np.tril(raw,-1).T
                    rhs = data[prefix+'rhs'].astype(np.float64).reshape(-1)
                    dx = data[prefix+'dx'].astype(np.float64).reshape(-1)
                    eigenvalues = np.linalg.eigvalsh(matrix)
                    residual = float(np.linalg.norm(matrix@dx-rhs) / max(np.linalg.norm(rhs),1e-30))
                    row = {'cell':name[:-4], 'iteration':iteration,
                           'lambda_min':float(eigenvalues[0]),
                           'relative_linear_residual':residual,
                           'finite':bool(np.isfinite(matrix).all() and np.isfinite(dx).all() and np.isfinite(rhs).all())}
                    row['PASS'] = bool(row['finite'] and row['lambda_min']>0 and residual<1e-3)
                    rows.append(row)
    report = {'state':state, 'rows':rows, 'PASS':len(rows)==16 and all(row['PASS'] for row in rows),
              'residual_stop_threshold':1e-3, 'endpoint_tolerance_unchanged':True,
              'native_solver_info_not_recorded':True}
    (ROOT/'05_analysis'/('HEALTH_'+state+'.json')).write_text(json.dumps(report,indent=2))
    if not report['PASS']:
        raise RuntimeError('CPU native linear-system health check failed: '+state)
    c.log('NUMERICAL_HEALTH_CHECKED',state=state,rows=len(rows),max_relative_residual=max(x['relative_linear_residual'] for x in rows))

def main():
    with LOCK.open('x') as stream:
        stream.write(json.dumps({'pid':os.getpid(),'unix':time.time()}))
    c.log('SUPERVISOR_ORCHESTRATION_RESUMED',pid=os.getpid(),numerical_retry=False,
          reason='previous local tool process no longer exists; remote completed attempts preserved')
    try:
        for arm in c.ARMS:
            retired = c.remote("import pathlib,json\np=pathlib.Path("+repr(c.REMOTE+'/retirement/'+arm+'.json')+")\nprint(json.dumps({'retired':p.exists() and json.loads(p.read_text()).get('completed',False)}))",'RESUME_RETIRE_CHECK_'+arm)
            if retired['retired']:
                for rgb in c.RGB:
                    state=arm+'_RGB%03d'%rgb
                    c.collect(state,'snapshot');c.collect(state,'result');health(state)
                c.log('COMPLETED_ARM_ALREADY_ARCHIVED',arm=arm)
                continue
            status=c.status(arm)
            if not status['exists']:
                c.launch(arm)
            c.wait_finish(arm)
            proofs=[]
            for rgb in c.RGB:
                state=arm+'_RGB%03d'%rgb
                proofs.append(c.collect(state,'snapshot'))
                status=c.status(arm,state)
                if not status['exists']:
                    c.launch(arm,state)
                c.wait_finish(arm,state)
                proofs.append(c.collect(state,'result'))
                health(state)
            c.retire(arm,proofs)
        c.log('ALL_AUTHORIZED_GPU_WORK_COMPLETE',prefixes=4,states=12,mechanism_native_calls=144,new_frame_steps=1532,final_BA=False,filler=False)
        (ROOT/'04_results/SUPERVISOR_SUCCESS.json').write_text(json.dumps({'PASS':True,'prefixes':4,'contexts':12,'native_calls':144,'automatic_numerical_retries':0,'setup_attempts':2,'orchestration_resumptions':1,'shutdown_performed':False},indent=2))
    except BaseException as exc:
        c.log('STOPPED',error=str(exc))
        (ROOT/'04_results/SUPERVISOR_STOP_RESUME02.json').write_text(json.dumps({'error':str(exc),'traceback':traceback.format_exc(),'no_next_run_started':True},indent=2))
        raise
    finally:
        LOCK.unlink()

if __name__=='__main__':main()
