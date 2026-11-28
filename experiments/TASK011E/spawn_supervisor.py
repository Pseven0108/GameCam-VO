"""Fail closed when a registered native child exits unsuccessfully.

This module imports no model, torch, or CUDA code and never changes numerical
inputs. The caller registers only its own multiprocessing Process objects.
"""
import json
import os
import threading
import time
from pathlib import Path


def failed_children(processes):
    result = []
    for process in tuple(processes):
        if process.pid is not None and process.exitcode not in (None, 0):
            result.append(dict(pid=process.pid, exit_code=process.exitcode))
    return result


def watch_children(processes, output, stop, fatal=os._exit, interval=0.2):
    while not stop.wait(interval):
        failed = failed_children(processes)
        if not failed:
            continue
        path = Path(output) / 'CHILD_PROCESS_FAILURE.json'
        value = dict(status='ENGINEERING_CHILD_FAILURE', children=failed,
                     observed_unix=time.time(), observer_only=True,
                     numerical_configuration_changed=False)
        temporary = path.with_suffix('.json.partial')
        temporary.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
        temporary.replace(path)
        # A dead spawn child can leave native shared counters waiting forever.
        # The independent launcher reaps this driver's private process group.
        fatal(70)
        return


def start_child_watchdog(processes, output):
    stop = threading.Event()
    thread = threading.Thread(target=watch_children,
                              args=(processes, output, stop),
                              daemon=True, name='task011e-child-health')
    thread.start()
    return stop, thread

