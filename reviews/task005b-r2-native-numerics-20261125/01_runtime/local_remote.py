"""Pinned SSH bridge with independently saved R2 receipts; no secret output."""
import sys, pathlib, json, subprocess, time, shlex, importlib.util, os
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
spec=importlib.util.spec_from_file_location('prior_ssh_bridge',OLD/'01_runtime/ssh_execute.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
def run(script,label,python='/usr/bin/python3',gpu=False,timeout=90):
 out=ROOT/'00_intake';out.mkdir(exist_ok=True)
 command='exec env PYTHONDONTWRITEBYTECODE=1 '+('' if gpu else 'CUDA_VISIBLE_DEVICES= ')+shlex.quote(python)+' -B -u -'
 started=time.time()
 with (out/(label+'.stdout.txt')).open('xb') as fo,(out/(label+'.stderr.txt')).open('xb') as fe:
  proc=subprocess.run(bridge.base()+['-o','ClearAllForwardings=yes',bridge.ssh.HOST,command],input=script,stdout=fo,stderr=fe,timeout=timeout,creationflags=bridge.ssh.CREATE)
 receipt={'exit_code':proc.returncode,'started_unix':started,'finished_unix':time.time(),'trust':bridge.ssh.verified(out/(label+'.stderr.txt')),'endpoint':'sc01-ssh.gpuhome.cc:30601','gpu_visibility_enabled':gpu}
 (out/(label+'.receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt),flush=True)
 if proc.returncode or not all(receipt['trust'].values()):raise RuntimeError('Remote command failed; preserve evidence, no auto retry')
 return (out/(label+'.stdout.txt')).read_text()
if __name__=='__main__':
 print(run(pathlib.Path(sys.argv[1]).read_bytes(),sys.argv[2]),flush=True)
