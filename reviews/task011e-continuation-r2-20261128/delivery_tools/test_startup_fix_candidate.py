"""Real stdlib spawn regression for a foreign generic-common import."""
import hashlib, importlib.util, json, multiprocessing, shutil, sys, tempfile, unittest
from pathlib import Path

BASE=Path(__file__).resolve().parent

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

def child(folder,queue):
    root=Path(folder);sys.path[:0]=[str(root/'foreign'),str(root/'stage')]
    sys.modules.pop('common',None);sys.modules.pop('task011e_io',None)
    foreign=__import__('common')
    auth=load(root/'stage/authorization.py','candidate_authorization_child')
    binding=load(root/'stage/native_binding.py','candidate_binding_child')
    try:auth.require_approved_runtime(None,'END_TO_END','test')
    except PermissionError:denied=True
    else:denied=False
    queue.put(dict(auth=str(auth.TASK),binding=str(binding.TASK),foreign=str(foreign.TASK),
                   denied=denied,torch_imported='torch' in sys.modules))

class ImportIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='task011e-import-',dir='D:/aaa/tmp/gamecam-vo')
        self.root=Path(self.tmp.name);(self.root/'foreign').mkdir();(self.root/'stage').mkdir()
        (self.root/'foreign/common.py').write_text('from pathlib import Path\nTASK=Path(__file__).parent\ndef sha(p): return "foreign"\n',encoding='utf-8')
        for p in (BASE/'startup_import_fix_candidate').glob('*.py'):shutil.copy2(p,self.root/'stage'/p.name)
        self.path=sys.path.copy();self.saved={k:sys.modules.get(k) for k in ('common','task011e_io')}
        sys.path[:0]=[str(self.root/'foreign'),str(self.root/'stage')]
        for k in self.saved:sys.modules.pop(k,None)
        self.foreign=__import__('common')
    def tearDown(self):
        sys.path[:]=self.path
        for k,v in self.saved.items():
            sys.modules.pop(k,None)
            if v is not None:sys.modules[k]=v
        self.tmp.cleanup()
    def auth(self):return load(self.root/'stage/authorization.py','candidate_auth_test')
    def test_original_failure_reproduced(self):
        a=load(BASE/'repo/experiments/TASK011E/authorization.py','original_auth_test')
        self.assertEqual(a.TASK,self.root/'foreign')
    def test_authorization_uses_own_directory(self):self.assertEqual(self.auth().TASK,self.root/'stage')
    def test_binding_uses_own_directory(self):
        self.assertEqual(load(self.root/'stage/native_binding.py','candidate_binding_test').TASK,self.root/'stage')
    def test_foreign_module_preserved(self):
        self.auth();self.assertIs(sys.modules['common'],self.foreign)
    def test_hash_matches_original_contract(self):
        p=self.root/'bytes.bin';p.write_bytes(b'abc\x00\xff')
        self.assertEqual(self.auth().sha(p),hashlib.sha256(p.read_bytes()).hexdigest())
    def test_missing_authorization_fails_closed(self):
        with self.assertRaises(PermissionError):self.auth().require_approved_runtime(None,'END_TO_END','x')
    def test_nonexistent_authorization_fails_closed(self):
        with self.assertRaises(PermissionError):self.auth().require_approved_runtime(self.root/'absent','END_TO_END','x')
    def test_real_spawn_preserves_stage_identity_and_gate(self):
        ctx=multiprocessing.get_context('spawn');q=ctx.Queue();p=ctx.Process(target=child,args=(str(self.root),q));p.start()
        result=q.get(timeout=20);p.join(timeout=20)
        self.assertEqual(p.exitcode,0);self.assertEqual(result['auth'],str(self.root/'stage'))
        self.assertEqual(result['binding'],str(self.root/'stage'));self.assertEqual(result['foreign'],str(self.root/'foreign'))
        self.assertTrue(result['denied']);self.assertFalse(result['torch_imported'])

if __name__=='__main__':unittest.main(verbosity=2)
