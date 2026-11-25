"""Remote detached wrapper: durable logs and exit code, no automatic retries."""
import pathlib,sys,os,subprocess,json,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
phase=sys.argv[1];assert phase in ['plain','trace','build']
log=ROOT/'evidence'/phase;log.mkdir(parents=True,exist_ok=False)
script=ROOT/('candidate/build_observer.py' if phase=='build' else 'tools/replay_r2.py')
argv=[sys.executable,'-B','-u',str(script)]+([] if phase=='build' else ['--phase',phase])
start=time.time()
with (log/'stdout.txt').open('xb') as fo,(log/'stderr.txt').open('xb') as fe:
 proc=subprocess.run(argv,stdout=fo,stderr=fe,cwd=ROOT,env=os.environ.copy())
(log/'PROCESS_RECEIPT.json').write_text(json.dumps({'exit_code':proc.returncode,'phase':phase,'seconds':time.time()-start,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'automatic_retry':False},indent=2)+'\n')
raise SystemExit(proc.returncode)
