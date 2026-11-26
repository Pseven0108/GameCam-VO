"""Retrieve only this run's stage artifacts and verify remote SHA-256."""
import argparse,hashlib,json,pathlib,subprocess
from remote_io import ROOT,HOST,PORT,SSH,REMOTE_ROOT,ssh_options
from remote_start import cmd
def main():
 p=argparse.ArgumentParser();p.add_argument('stage');a=p.parse_args()
 if a.stage not in ['smoke','smoke_qualified','pilot']:raise ValueError('Owned stage only')
 stage=REMOTE_ROOT+'/'+a.stage
 script="""import pathlib,hashlib,json
root=pathlib.Path(STAGE)
paths=list(sorted(root.glob('*')))+[pathlib.Path(LOGROOT)/(STAGENAME+'.stdout.txt'),pathlib.Path(LOGROOT)/(STAGENAME+'.stderr.txt'),pathlib.Path(LOGROOT)/(STAGENAME+'_launch.json')]
out=[]
for p in paths:
 if p.is_file():out.append({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps(out))
""".replace('STAGE)',repr(stage)+')').replace('LOGROOT',repr(REMOTE_ROOT+'/logs')).replace('STAGENAME',repr(a.stage))
 rows=json.loads(cmd('exec env CUDA_VISIBLE_DEVICES= /usr/bin/python3 -B -',script.encode()).decode())
 dest=ROOT/('01_smoke' if a.stage.startswith('smoke') else '02_pilot')/a.stage;dest.mkdir(parents=True,exist_ok=True)
 for row in rows:
  local=dest/pathlib.PurePosixPath(row['path']).name
  if local.exists():
   if hashlib.sha256(local.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Existing local artifact mismatch')
   continue
  result=subprocess.run([str(SSH.with_name('scp.exe')),'-q','-P',PORT,*ssh_options(),'root@'+HOST+':'+row['path'],str(local)],capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
  if result.returncode:raise RuntimeError('Readback transfer failed')
  if local.stat().st_size!=row['bytes'] or hashlib.sha256(local.read_bytes()).hexdigest()!=row['sha256']:raise RuntimeError('Readback SHA mismatch')
 report=dest/'DOWNLOAD_VERIFICATION.json'
 with report.open('x',encoding='utf-8') as f:f.write(json.dumps({'files':rows,'all_verified':True,'remote_history_modified':False},indent=2)+'\n')
 print(json.dumps({'stage':a.stage,'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'SHA256':'PASS'}))
if __name__=='__main__':main()
