"""Actual CPU regressions for isolated imports and native-child fail-fast."""
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest

BASE=Path(__file__).resolve().parent
TASK=BASE/'repo/experiments/TASK011E'
if not TASK.exists():TASK=BASE


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def import_child(task,queue):
    sys.path.insert(0,task)
    foreign=types.ModuleType('common');foreign.TASK=Path('/foreign/frozen/TASK011B')
    foreign.sha=lambda path:'WRONG';sys.modules['common']=foreign
    a=load('task011e_test_authorization',Path(task)/'authorization.py')
    b=load('task011e_test_binding',Path(task)/'native_binding.py')
    queue.put(dict(task=str(a.TASK),binding=str(b.TASK),foreign_preserved=sys.modules['common'] is foreign,
                   torch_imported='torch' in sys.modules))


def broken_child():
    raise ImportError('Synthetic spawn startup failure; no model imported')


def watched_driver(out):
    sys.path.insert(0,str(TASK))
    from spawn_supervisor import start_child_watchdog
    ctx=mp.get_context('spawn');process=ctx.Process(target=broken_child)
    processes=[process];start_child_watchdog(processes,Path(out));process.start()
    # Simulates a native shared-counter wait after a child import failure.
    while True:time.sleep(.1)


class ReleaseRegression(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='task011e-r3-')
        self.output=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_unique_helper_identity(self):
        helper=load('task011e_test_io',TASK/'task011e_io.py')
        self.assertEqual(helper.TASK,TASK.resolve())
    def test_sha_preserves_raw_bytes(self):
        helper=load('task011e_test_io_sha',TASK/'task011e_io.py')
        p=self.output/'data';p.write_bytes(b'\x00a\xff\n')
        self.assertEqual(helper.sha(p),hashlib.sha256(p.read_bytes()).hexdigest())
    def test_real_spawn_foreign_common_isolation(self):
        context=mp.get_context('spawn');queue=context.Queue();child=context.Process(target=import_child,args=(str(TASK),queue))
        child.start();record=queue.get(timeout=20);child.join(timeout=20)
        self.assertEqual(child.exitcode,0);self.assertEqual(record['task'],str(TASK.resolve()))
        self.assertEqual(record['binding'],str(TASK.resolve()));self.assertTrue(record['foreign_preserved'])
        self.assertFalse(record['torch_imported'])
    def test_missing_approval_rejected(self):
        sys.path.insert(0,str(TASK))
        auth=load('task011e_test_auth_absent',TASK/'authorization.py')
        with self.assertRaises(PermissionError):auth.require_approved_runtime(None,'END_TO_END','x')
    def test_R2_approval_rejected_before_model_access(self):
        sys.path.insert(0,str(TASK));auth=load('task011e_test_auth_old',TASK/'authorization.py')
        value=json.loads((TASK/'RUNTIME_AUTHORIZATION.json').read_text(encoding='utf-8'))
        value['stage']='TASK011E_FAST_285_CONTINUATION_R2';path=self.output/'old.json';path.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(PermissionError):auth.require_approved_runtime(path,'END_TO_END',value['approved_job_keys'][-1])
    def test_watchdog_ignores_not_started_success_and_running(self):
        module=load('task011e_test_supervisor_ok',TASK/'spawn_supervisor.py')
        processes=[types.SimpleNamespace(pid=None,exitcode=1),types.SimpleNamespace(pid=1,exitcode=0),types.SimpleNamespace(pid=2,exitcode=None)]
        self.assertEqual(module.failed_children(processes),[])
    def test_watchdog_detects_nonzero_and_signal(self):
        module=load('task011e_test_supervisor_bad',TASK/'spawn_supervisor.py')
        processes=[types.SimpleNamespace(pid=3,exitcode=1),types.SimpleNamespace(pid=4,exitcode=-11)]
        self.assertEqual(module.failed_children(processes),[dict(pid=3,exit_code=1),dict(pid=4,exit_code=-11)])
    def test_watchdog_records_failure_before_exit(self):
        module=load('task011e_test_supervisor_record',TASK/'spawn_supervisor.py')
        result=[];stop=threading.Event()
        module.watch_children([types.SimpleNamespace(pid=9,exitcode=2)],self.output,stop,fatal=result.append,interval=.001)
        self.assertEqual(result,[70]);self.assertEqual(json.loads((self.output/'CHILD_PROCESS_FAILURE.json').read_text())['children'][0]['exit_code'],2)
    def test_real_spawn_failure_ends_waiting_parent(self):
        start=time.monotonic()
        result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--watched-driver',str(self.output)],capture_output=True,timeout=25)
        self.assertEqual(result.returncode,70);self.assertLess(time.monotonic()-start,25)
        self.assertTrue((self.output/'CHILD_PROCESS_FAILURE.json').exists())
    @unittest.skipUnless(sys.platform=='linux','Linux process groups exercised on server CPU')
    def test_private_group_cleanup_does_not_signal_unrelated_process(self):
        module=load('task011e_test_launcher',TASK/'process_launcher.py')
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(40)'])
        try:
            with (self.output/'stdout').open('wb') as out,(self.output/'stderr').open('wb') as err:
                code=module.run_native([sys.executable,'-c','import sys;sys.exit(7)'],out,err,dict(os.environ),str(self.output),self.output/'receipt.json')
            self.assertEqual(code,7);self.assertIsNone(unrelated.poll())
            self.assertEqual(json.loads((self.output/'receipt.json').read_text())['exit_code'],7)
        finally:unrelated.terminate();unrelated.wait(timeout=10)
    def test_frozen_order_and_controller_unchanged(self):
        value=json.loads((BASE/'PREPARATION_RECEIPT.json').read_text()) if (BASE/'PREPARATION_RECEIPT.json').exists() else None
        expected='ab4d924237a004acdc0a8f5926ae8c1ed7553b4255d6e200b48824aabef7a0ca'
        self.assertEqual(hashlib.sha256((TASK/'configs/EXECUTION_ORDER.csv').read_bytes()).hexdigest(),expected)
        if value:self.assertFalse(value['original_extension_or_baseline_changed'])


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--watched-driver':watched_driver(sys.argv[2])
    else:unittest.main(verbosity=2)
