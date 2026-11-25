import pathlib,subprocess,sys,os,json,time
r=pathlib.Path(__file__).resolve().parents[1];name=sys.argv[sys.argv.index('--state')+1];log=r/'evidence'/('REPLAY_'+name);start=time.time()
p=subprocess.run([sys.executable,'-B','-u',str(r/'tools/replay_state.py'),'--state',name],env=os.environ.copy(),cwd=r)
receipt={'exit_code':p.returncode,'state':name,'seconds':time.time()-start,'automatic_retry':False,'success_exists':(r/'results'/name/'SUCCESS.json').exists()};(log/'PROCESS_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt));raise SystemExit(p.returncode)
