import pathlib,sys,subprocess,json,time,os
r=pathlib.Path(__file__).resolve().parents[1];mode,arm=sys.argv[1:3];out=r/'attempts'/arm
start=time.time();script='capture_prefix.py' if mode=='capture' else 'replay_state.py'
cmd=[sys.executable,'-B','-u',str(r/'tools'/script),'--arm',arm]
p=subprocess.run(cmd,cwd=os.getcwd(),env=os.environ.copy())
receipt={'exit_code':p.returncode,'mode':mode,'arm':arm,'seconds':time.time()-start,'wrapper_pid':os.getpid(),'automatic_retry':False,'success_exists':(out/'SUCCESS.json').exists()}
(out/'PROCESS_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({'event':'PROCESS_EXIT',**receipt}),flush=True);raise SystemExit(p.returncode)
