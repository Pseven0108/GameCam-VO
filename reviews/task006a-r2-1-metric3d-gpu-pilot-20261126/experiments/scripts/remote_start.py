"""Stage only owned research files; run one authorized isolated GPU process."""
import argparse,hashlib,json,pathlib,subprocess,sys,time
from remote_io import ROOT,SSH,HOST,PORT,REMOTE_ROOT,PY,ssh_options

def cmd(command,script=None,timeout=60):
 p=subprocess.run([str(SSH),'-T','-p',PORT,*ssh_options(),'root@'+HOST,command],input=script,
                  capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError('Remote research command failed: '+p.stderr.decode('utf-8',errors='replace')[:800])
 return p.stdout

def upload(source,dest):
 if not dest.startswith(REMOTE_ROOT+'/'):raise ValueError('Independent destination required')
 local=pathlib.Path(source)
 p=subprocess.run([str(SSH.with_name('scp.exe')),'-q','-P',PORT,*ssh_options(),str(local),'root@'+HOST+':'+dest],
                   capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError('SCP failed: '+p.stderr.decode('utf-8',errors='replace')[:800])
 return {'local':str(local),'remote':dest,'bytes':local.stat().st_size,'sha256':hashlib.sha256(local.read_bytes()).hexdigest()}

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['smoke','smoke_qualified','pilot']);p.add_argument('--prepare',action='store_true');a=p.parse_args()
 if a.prepare:
  script="import pathlib,json; p=pathlib.Path("+repr(REMOTE_ROOT)+");p.mkdir(exist_ok=False);[(p/x).mkdir() for x in ['control','logs','inputs']];print(json.dumps({'created':str(p)}))"
  print(cmd('exec env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -',script.encode()).decode())
 records=[]
 script_name='metric3d_pilot.py' if a.stage=='smoke' else 'metric3d_pilot_qualified.py'
 manifest_stage='smoke' if a.stage.startswith('smoke') else a.stage
 for local,name in [(ROOT/'experiments/scripts/metric3d_pilot.py',script_name),
                    (ROOT/('experiments/configs/'+manifest_stage.upper()+'_MANIFEST.json'),a.stage+'_manifest.json')]:
  dest=REMOTE_ROOT+'/control/'+name
  # Existing identical scripts may be reused for pilot; mismatches stop.
  check="import pathlib,hashlib; p=pathlib.Path("+repr(dest)+"); print(hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'MISSING')"
  old=cmd('exec env CUDA_VISIBLE_DEVICES= /usr/bin/python3 -B -',check.encode()).decode().strip()
  expected=hashlib.sha256(local.read_bytes()).hexdigest()
  if old=='MISSING':records.append(upload(local,dest))
  elif old==expected:records.append({'remote':dest,'sha256':expected,'reuse_identical':True})
  else:raise RuntimeError('Do not overwrite different staged research file')
 argv=[PY,'-B','-u',REMOTE_ROOT+'/control/'+script_name,'--manifest',REMOTE_ROOT+'/control/'+a.stage+'_manifest.json','--out',REMOTE_ROOT+'/'+a.stage]
 if a.stage.startswith('smoke'):argv.append('--smoke')
 launch="""import os,pathlib,subprocess,json,hashlib
root=pathlib.Path(ROOT_VALUE)
stage=STAGE_VALUE
for item in EXPECTED_VALUE:
 p=pathlib.Path(item['remote'])
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
receipt=root/'logs'/(stage+'_launch.json')
assert not receipt.exists(), 'No automatic retry/overwrite of a launched stage'
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
with (root/'logs'/(stage+'.stdout.txt')).open('xb') as fo,(root/'logs'/(stage+'.stderr.txt')).open('xb') as fe:
 p=subprocess.Popen(ARGV_VALUE,env=env,cwd=root,stdout=fo,stderr=fe,start_new_session=True)
 data={'pid':p.pid,'stage':stage,'argv':ARGV_VALUE,'CPU_only':False,'GPU_inference_authorized':True,'model':'Metric3D only','no_SLAM':True}
 with receipt.open('x') as f:json.dump(data,f,indent=2)
 print(json.dumps(data))
""".replace('ROOT_VALUE',repr(REMOTE_ROOT)).replace('STAGE_VALUE',repr(a.stage)).replace('EXPECTED_VALUE',repr(records)).replace('ARGV_VALUE',repr(argv))
 result=cmd('exec env CUDA_VISIBLE_DEVICES= /usr/bin/python3 -B -',launch.encode())
 (ROOT/'experiments/logs'/(a.stage+'_launch.receipt.json')).write_bytes(result)
 print(result.decode())

if __name__=='__main__':main()
