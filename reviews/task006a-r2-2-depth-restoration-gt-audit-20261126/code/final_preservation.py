"""Recheck the sealed input identities and the CPU-only remote outputs."""
from common import *
from remote_transport import run,REMOTE

def main():
    cpu_only()
    before=json.loads((ROOT/'00_evidence/PRESERVATION_BEFORE.json').read_text('utf-8'))
    files=[]
    for r in before['files']:
        p=pathlib.Path(r['path']);actual=sha(p)
        if actual!=r['sha256'] or p.stat().st_size!=r['bytes']:
            raise RuntimeError('Protected input changed: '+str(p))
        files.append({'path':r['path'],'bytes':r['bytes'],'sha256':actual,'verified':True})
    dump(ROOT/'00_evidence/PRESERVATION_AFTER.json',{'files':files,'checked':len(files),'changed':0,
      'sealed_R2_1_entries_checked':before['sealed_R2_1_entries_checked'],'status':'PASS'})
    script='''import hashlib,json,pathlib,shutil
root=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1')
rows=[]
for sub in ['smoke_qualified','pilot']:
    receipt=json.loads((root/sub/'INFERENCE_RECEIPT.json').read_text())
    for r in receipt['results']:
        p=root/sub/pathlib.PurePosixPath(r['output']).name
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h!=r['sha256']:raise RuntimeError('Sealed output changed')
        rows.append({'sample_id':r['sample']['sample_id'],'sha256':h,'verified':True})
out=pathlib.Path('/root/rivermind-data/GAMECAM_TASK006A_R2_2_CPU_RESTORE_20261126_R1')
current=[]
for p in sorted(out.iterdir()):
    if p.is_file():current.append({'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps({'sealed_R2_1_outputs':rows,'R2_2_outputs':current,'free_bytes':shutil.disk_usage(out).free,
 'CUDA_or_GPU_API_called':False,'model_loaded':False,'instance_shutdown_or_reboot_performed':False}))
'''
    remote=json.loads(run(script,'FINAL_REMOTE_READONLY',python='/usr/bin/python3'))
    local=json.loads((ROOT/'02_restoration/torch_CPU/DOWNLOAD_VERIFICATION.json').read_text('utf-8'))
    index={r['name']:r for r in remote['R2_2_outputs']}
    for r in local['files']:
        if index[r['name']]['sha256']!=r['sha256'] or index[r['name']]['bytes']!=r['bytes']:
            raise RuntimeError('Remote CPU output changed')
    dump(ROOT/'00_evidence/REMOTE_FINAL_PRESERVATION.json',remote)
    print(json.dumps({'local_protected':len(files),'remote_sealed_outputs':len(remote['sealed_R2_1_outputs']),
      'remote_CPU_outputs':len(local['files']),'changed':0,'remote_free_bytes':remote['free_bytes']}))

if __name__=='__main__':main()
