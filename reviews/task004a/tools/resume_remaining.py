import sys,json,pathlib,base64,shlex,subprocess,os
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from transport import PRE,ssh_base,HOST,CREATE,verified
utc=lambda:datetime.now(timezone.utc).isoformat()
authorization=dict(schema='TASK004A_DATA_PRIORITY_RESUME_V1',utc=utc(),user_message='可以暂时不用管可视化，我现在暂时只要消融后的结果和数据',remaining=['E0','E8','E6','E1','E2'],existing_preserved=['E3','E4','E7'],retry_any_model=False,algorithm_or_yaml_changed=False,browser_rendering_gate_waived=True,native_rerun_writer_retained=True,shutdown_authorized=False)
with (ROOT/'RESUME_AUTHORIZATION_DATA_PRIORITY.json').open('x',encoding='utf-8') as f:json.dump(authorization,f,indent=2,ensure_ascii=False)
boot=json.loads((ROOT/'bootstrap/evidence/BOOTSTRAP_PASS.json').read_text());auth=json.loads((ROOT/'release/AUTHORIZATION.json').read_text())
payload=dict(root=auth['remote_root'],authorization=authorization,remaining=authorization['remaining'],viewer_argv=boot['viewer']['native_identity']['argv'],launcher_source=(ROOT/'tools/remote_execute_one.py').read_text())
code=(ROOT/'tools/resume_remote.py').read_text();loader="import sys,base64;exec(compile(base64.b64decode(sys.stdin.readline()),'<data-priority-resume>','exec'))"
command='exec env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/python3 -I -B -u -c '+shlex.quote(loader)
errfile=ROOT/'evidence/resume_remaining.ssh.stderr.txt'
with errfile.open('xb') as err,(ROOT/'evidence/resume_remaining.stdout.txt').open('xb') as out:
 p=subprocess.Popen(ssh_base(PRE)+['-o','ClearAllForwardings=yes',HOST,command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,creationflags=CREATE)
 p.stdin.write(base64.b64encode(code.encode())+b'\n'+json.dumps(payload).encode()+b'\n');p.stdin.close()
 for line in p.stdout:
  out.write(line);out.flush();print(line.decode(errors='replace').rstrip(),flush=True)
 rc=p.wait()
trust=verified(errfile)
with (ROOT/'evidence/resume_remaining.transport_receipt.json').open('x') as f:json.dump(dict(exit_code=rc,trust=trust,utc=utc()),f,indent=2)
assert all(trust.values()),'SSH identity verification failed'
sys.exit(rc)