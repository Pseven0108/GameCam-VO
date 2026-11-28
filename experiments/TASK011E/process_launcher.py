"""Run exactly one native driver in a private, owned Linux process group."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def run_native(command, stdout, stderr, env, cwd, audit):
    if sys.platform != 'linux':
        raise RuntimeError('Formal native launch requires Linux')
    child = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env,
                             cwd=cwd, start_new_session=True)
    group = child.pid
    if os.getpgid(child.pid) != group:
        raise RuntimeError('Native driver process-group ownership not established')
    record = dict(driver_pid=child.pid, private_process_group=group,
                  started_unix=time.time(), automatic_retry=False)
    try:
        record['exit_code'] = child.wait()
        return record['exit_code']
    finally:
        # Only descendants remaining in the newly created driver session are
        # signalled. Never inspect or terminate unrelated GPU/SSH services.
        try:
            os.killpg(group, signal.SIGTERM)
            record['remaining_owned_group_signalled'] = True
        except ProcessLookupError:
            record['remaining_owned_group_signalled'] = False
        record['finished_unix'] = time.time()
        Path(audit).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')

