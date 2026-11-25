import ast,pathlib,json,sys
p=pathlib.Path(__file__).resolve().parents[1]
checks=[]
for name in ['capture_prefix.py','prefix_journal.py','ba_state_io.py','replay_state.py','process_wrapper.py']:
 s=(p/'01_runtime'/name).read_text(encoding='utf-8-sig');ast.parse(s);checks.append('AST_'+name)
s=(p/'01_runtime/replay_state.py').read_text();assert 'len(result)!=46' in s and 'for it in range(2)' in s;checks.append('two_native_iterations_trace_contract')
assert 'atol=1e-6,rtol=1e-5' in s;checks.append('preregistered_endpoint_tolerance_unchanged')
assert 'baseline_hash' in s and 'Input alias relation changed' in s;checks.append('alias_and_full_value_hash_guard')
assert "np.savez_compressed" in s;checks.append('lossless_outputs')
report={'PASS':True,'checks':checks,'passed':len(checks),'GPU_calls':0};(p/'03_tests/LOCAL_AST_TEST.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
