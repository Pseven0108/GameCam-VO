import ast, json, tempfile, pathlib, sys, copy
root=pathlib.Path(__file__).resolve().parents[1]
source=(root/'bootstrap/remote_session.py').read_text()
tree=ast.parse(source); tree.body=tree.body[:-1]
ns={'__name__':'unit_fixture'};exec(compile(tree,'remote_session','exec'),ns)
rows=[dict(table='tcp',address_hex='0100007F',port=p,inode=str(p)) for p in [9875,9876,9877]]
results=[]
with tempfile.TemporaryDirectory() as d:
    native=pathlib.Path(d)/'rerun'; native.touch(); ns['NATIVE']=native
    argv=['rerun','--bind','127.0.0.1']; ns['ARGV']=argv
    valid=dict(pid=22,ppid=11,executable=str(native.resolve()),cwd=d,argv=[str(native),*argv[1:]])
    owned={r['inode'] for r in rows};owners={x:[22] for x in owned}
    for label,changes in [('valid',{}),('wrong_parent',{'ppid':12}),('wrong_exe',{'executable':'/tmp/fake'}),('wrong_cwd',{'cwd':'/'}),('wrong_args',{'argv':[str(native),'--bind','0.0.0.0']}),('wrong_argv0',{'argv':['/tmp/fake',*argv[1:]]})]:
        doc={**valid,**changes}; passed=True
        try: ns['validate_child'](doc,11,pathlib.Path(d),rows,owned,owners)
        except AssertionError: passed=False
        results.append(dict(test=label,pass_=passed==(label=='valid')))
    for label,rr,oo,ow in [('wildcard',[{**rows[0],'address_hex':'00000000'},*rows[1:]],owned,owners),('ipv6',[{**rows[0],'table':'tcp6'},*rows[1:]],owned,owners),('missing_inode',rows,set(),owners),('extra_owner',rows,owned,{x:[22,33] for x in owned})]:
        rejected=False
        try: ns['validate_child'](valid,11,pathlib.Path(d),rr,oo,ow)
        except AssertionError: rejected=True
        results.append(dict(test=label,pass_=rejected))
for file in ['bootstrap/run_once.py','bootstrap/remote_session.py']:
    ast.parse((root/file).read_text()); results.append(dict(test='syntax_'+file,pass_=True))
doc=dict(mode='CPU_MOCK_ONLY_NO_REMOTE',results=results,passed=sum(r['pass_'] for r in results),total=len(results))
(root/'evidence/RELEASE_CPU_TESTS.json').write_text(json.dumps(doc,indent=2))
print(json.dumps(doc));sys.exit(0 if all(r['pass_'] for r in results) else 1)
