import base64,io,json,zipfile,sys
from remote_access import ROOT,run
remote='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1'
label=sys.argv[1] if len(sys.argv)>1 else 'v2'
code=r'''
import base64,io,json,os,pathlib,subprocess,sys,zipfile
root=pathlib.Path(REMOTE_ROOT);label=LABEL;raw=sys.stdin.buffer.read();script=root/('tools/probe_file_sharing_'+label+'.py');script.write_bytes(raw)
q=subprocess.run([sys.executable,'-B',str(script),label],cwd=root,capture_output=True,timeout=200,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'))
(root/('logs/API_PROBE_'+label+'.stdout.txt')).write_bytes(q.stdout);(root/('logs/API_PROBE_'+label+'.stderr.txt')).write_bytes(q.stderr)
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for p in (root/('artifacts/API_SHARING_PROBE_'+label)).rglob('*'):
  if p.is_file() and p.suffix!='.bin':z.write(p,p.relative_to(root).as_posix())
print(json.dumps({'exit_code':q.returncode,'stdout':q.stdout.decode(errors='replace'),'stderr':q.stderr.decode(errors='replace'),'evidence_b64':base64.b64encode(b.getvalue()).decode()}))
'''.replace('REMOTE_ROOT',repr(remote)).replace('LABEL',repr(label))
r=json.loads(run('API_SHARING_PROBE_'+label,code,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',input_bytes=(ROOT/'tools/probe_file_sharing.py').read_bytes(),timeout=220))
raw=base64.b64decode(r.pop('evidence_b64'))
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        p=ROOT/'evidence'/n;assert p.resolve().is_relative_to(ROOT.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(n))
(ROOT/('evidence/API_PROBE_RECEIPT_'+label+'.json')).write_text(json.dumps(r,indent=2))
data=json.loads((ROOT/('evidence/artifacts/API_SHARING_PROBE_'+label+'/PROBE_RESULTS.json')).read_text())
print(json.dumps({'exit_code':r['exit_code'],'torch':data['torch'],'cases':[{'strategy':x['strategy'],'transport':x['transport'],'file_backing_preserved':x['file_backing_preserved'],'parent_mapping':x['parent_after']['mapping'],'child_exit':x['child_exit_code']} for x in data['results']],'cuda_initialized':data['cuda_initialized']},indent=2))
if r['exit_code']:raise SystemExit(1)
