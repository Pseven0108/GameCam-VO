"""Run one CPU validation with immutable output paths and an explicit exit receipt."""
import base64
import json
import sys

from remote_cpu import ROOT, call


REMOTE = r'''
import base64, hashlib, json, os, pathlib, subprocess, sys, time
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
data=json.load(sys.stdin)
out=root/'cpu_tests'/data['label']
out.mkdir(exist_ok=False)
script=out/data['script_name']
script.write_bytes(base64.b64decode(data['script'],validate=True))
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
env=dict(os.environ,PYTHONPATH=':'.join(str(p) for p in (root,root/'source_candidate',root/'operational')),
    CUDA_VISIBLE_DEVICES='',GAMECAM_NATIVE_WORKSPACE=str(root),PYTHONHASHSEED='43',PYTHONDONTWRITEBYTECODE='1',
    OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MPLBACKEND='Agg')
start=time.time()
with (out/'process.stdout.txt').open('xb') as stdout,(out/'process.stderr.txt').open('xb') as stderr:
    proc=subprocess.Popen([python,'-B','-u',str(script),str(out)],env=env,
        cwd=root/'source_candidate',stdout=stdout,stderr=stderr)
    (out/'PROCESS_STARTED.json').write_text(json.dumps({'pid':proc.pid,'start_unix':start,'CUDA_VISIBLE_DEVICES':env['CUDA_VISIBLE_DEVICES']}))
    exit_code=proc.wait(timeout=data['timeout'])
receipt={'case':data['label'],'exit_code':exit_code,'runtime_seconds':time.time()-start,
    'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
    'stdout_sha256':hashlib.sha256((out/'process.stdout.txt').read_bytes()).hexdigest(),
    'stderr_sha256':hashlib.sha256((out/'process.stderr.txt').read_bytes()).hexdigest()}
(out/'PROCESS_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
'''


if __name__ == '__main__':
    script, label, seconds = sys.argv[1:]
    assert label.replace('_', '').isalnum() and script in ('test_format.py', 'test_configdict.py', 'model_roundtrip.py', 'test_stage_runner.py', 'test_driver_integration.py', 'test_stage_guard.py')
    payload = {
        'label': label,
        'script_name': script,
        'script': base64.b64encode((ROOT / 'tools' / script).read_bytes()).decode(),
        'timeout': int(seconds),
    }
    result = json.loads(call(label, REMOTE, input_bytes=json.dumps(payload).encode(), timeout=int(seconds) + 60))
    print(json.dumps(result))
    raise SystemExit(result['exit_code'] != 0)
