import pathlib,json,hashlib,base64,ast
r=pathlib.Path(__file__).resolve().parents[1];runtime=r/'01_runtime'
p=runtime/'replay_state.py';s=p.read_text();assert s.count("out=ROOT/'results'/name")==1
s=s.replace("out=ROOT/'results'/name","out=ROOT/'results_context02'/name")
assert s.count(' try:main()')==1
s=s.replace(' try:main()'," try:\n  import torch\n  with torch.no_grad():main()")
new=runtime/'replay_state_context02.py';new.write_text(s)
w=(runtime/'replay_wrapper.py').read_text().replace("('REPLAY_'+name)","('REPLAY_CONTEXT02_'+name)").replace("tools/replay_state.py","tools/replay_state_context02.py").replace("r/'results'/name","r/'results_context02'/name")
(runtime/'replay_context02_wrapper.py').write_text(w)
a=(runtime/'collect_owned_artifact.py').read_text().replace("('snapshots' if kind=='snapshot' else 'results')","('snapshots' if kind=='snapshot' else 'results_context02')")
(runtime/'collect_context02_artifact.py').write_text(a)
t=(runtime/'launch_replay_template.py.txt').read_text().replace("('REPLAY_'+name)","('REPLAY_CONTEXT02_'+name)").replace("tools/replay_wrapper.py","tools/replay_context02_wrapper.py")
(runtime/'launch_context02_template.py.txt').write_text(t)
(runtime/'launch_context02_D1_S1_RGB019.py').write_text(t.replace('name=STATE',"name='D1_S1_RGB019'"))
files=['replay_state_context02.py','replay_context02_wrapper.py']
contents={x:base64.b64encode((runtime/x).read_bytes()).decode() for x in files}
remote="import pathlib,base64,hashlib,json\nr=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')\nfiles="+repr(contents)+"\nresult={}\nfor name,encoded in files.items():\n p=r/'tools'/name\n with p.open('xb') as f:f.write(base64.b64decode(encoded))\n result[name]=hashlib.sha256(p.read_bytes()).hexdigest()\n(r/'results_context02').mkdir(exist_ok=False)\nprint(json.dumps(result))\n"
(runtime/'deploy_context02.py').write_text(remote)
for x in files+['collect_context02_artifact.py','launch_context02_D1_S1_RGB019.py','deploy_context02.py']:ast.parse((runtime/x).read_text())
(r/'03_tests/CONTEXT02_AST_CHECK.json').write_text(json.dumps({'files':files,'ast':'PASS','native_math_or_tolerances_changed':False,'source_results_retained':True},indent=2))
print('Prepared isolated grad-context entry; original setup attempt retained.')
