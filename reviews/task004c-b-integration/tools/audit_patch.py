import ast,difflib,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'source_before';CAND=ROOT/'source_candidate'
changed=[];lines=[]
def native_calls(p):
    tree=ast.parse(p.read_text(encoding='utf-8'))
    return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='droid_backends']
for p in sorted(CAND.rglob('*')):
    if not p.is_file() or '.git' in p.parts:continue
    before=BASE/p.relative_to(CAND)
    if not before.is_file():continue
    if before.read_bytes()!=p.read_bytes():
        name=p.relative_to(CAND).as_posix();changed.append(name)
        assert p.suffix=='.py','Non-Python original source changed'
        a=before.read_text(encoding='utf-8');b=p.read_text(encoding='utf-8');ast.parse(b)
        lines.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
cuda=[p for p in BASE.rglob('*') if p.is_file() and p.suffix in ('.cu','.cpp','.c','.h','.hpp')]
assert all(p.read_bytes()==(CAND/p.relative_to(BASE)).read_bytes() for p in cuda)
assert native_calls(BASE/'src/depth_video.py')==native_calls(CAND/'src/depth_video.py')
assert (BASE/'src/geom/ba.py').read_bytes()==(CAND/'src/geom/ba.py').read_bytes()
assert (BASE/'src/modules/droid_net/corr.py').read_bytes()==(CAND/'src/modules/droid_net/corr.py').read_bytes()
(ROOT/'artifacts/NATIVE_CONTROL_INTERFACE.patch').write_text(''.join(lines),encoding='utf-8')
(ROOT/'evidence/PATCHED_FILES.json').write_text(json.dumps(changed,indent=2))
r={'changed_source_files':changed,'cuda_and_cpp_files_unchanged':len(cuda),'native_extension_call_AST_unchanged':True,
   'python_BA_math_byte_identical':True,'correlation_implementation_byte_identical':True,'original_baseline_written':False}
(ROOT/'evidence/ALGORITHM_PRESERVATION.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r))
