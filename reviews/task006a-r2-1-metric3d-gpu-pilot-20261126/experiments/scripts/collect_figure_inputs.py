"""Retrieve ten already-existing VIPER RGB inputs, no new dataset request."""
import hashlib,json,pathlib,subprocess
from remote_io import ROOT,SSH,PORT,HOST,ssh_options
def main():
 rows=[]
 for receipt in [ROOT/'01_smoke/smoke_qualified/INFERENCE_RECEIPT.json',ROOT/'02_pilot/pilot/INFERENCE_RECEIPT.json']:
  for result in json.loads(receipt.read_text())['results']:
   item=result['sample']
   if item['dataset']=='VIPER':
    local=ROOT/'inputs/VIPER'/(item['sample_id']+'.jpg');local.parent.mkdir(exist_ok=True,parents=True)
    if not local.exists():
     p=subprocess.run([str(SSH.with_name('scp.exe')),'-q','-P',PORT,*ssh_options(),'root@'+HOST+':'+item['rgb_path'],str(local)],capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
     if p.returncode:raise RuntimeError('RGB readback failed')
   else:local=pathlib.Path(item['local_RGB_path'])
   h=hashlib.sha256(local.read_bytes()).hexdigest()
   if h!=item['rgb_sha256']:raise RuntimeError('Figure/input RGB mismatch')
   rows.append({'sample_id':item['sample_id'],'path':str(local),'sha256':h,'dataset':item['dataset']})
 with (ROOT/'evidence/FIGURE_INPUT_IDENTITY.json').open('x',encoding='utf-8') as f:f.write(json.dumps({'files':rows,'all_match_inference_inputs':True},indent=2)+'\n')
 print(json.dumps({'RGB_inputs':len(rows),'identities':'PASS','new_external_RGB_download':False}))
if __name__=='__main__':main()
