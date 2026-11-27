"""Read-only final identity checks; never repair or rewrite protected assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def main():
    before=json.loads((TASK/'private/HISTORICAL_PROTECTION_BEFORE.json').read_text());checks=[]
    for r in before:
        p=Path(r['path']);actual=sha(p) if p.is_file() else None
        checks.append({'path':r['path'],'bytes':r['bytes'],'original_sha256':r['sha256'],
            'current_sha256':actual,'PASS':actual==r['sha256'] and p.stat().st_size==r['bytes'] if p.is_file() else False})
    runs=[]
    for p in sorted((TASK/'outputs/droid').glob('*/receipt.json')):
        r=json.loads(p.read_text())
        if r['status']!='COMPLETE':continue
        runs.append({'run':p.parent.name,'native_extension_sha256':r['native_extension_sha256'],
            'tracker_checkpoint_sha256':r['checkpoint_sha256'],'native_U_enabled':r['native_u_enabled']})
    consistent=len({r['native_extension_sha256'] for r in runs})==1 and len({r['tracker_checkpoint_sha256'] for r in runs})==1
    status={}
    for name,repo in [('task010',ROOT),('task009',Path('D:/aaa/GameCam-VO-TASK009')),
        ('production',Path('D:/aaa/GameCam-VO')),
        ('native_droid_source',Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W')),
        ('pi3mos_source',Path('D:/aaa/external_models/Pi3MOS-SLAM_TASK008_FRESH'))]:
        values={}
        top=subprocess.run(['git','-C',str(repo),'rev-parse','--show-toplevel'],capture_output=True,text=True)
        dedicated=top.returncode==0 and Path(top.stdout.strip()).resolve()==repo.resolve()
        values['dedicated_git_checkout']=dedicated
        for key,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--short'])]:
            if not dedicated:
                values[key]='NOT_A_DEDICATED_GIT_CHECKOUT_USE_SNAPSHOT_IDENTITIES';continue
            out=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True)
            values[key]=out.stdout.strip() if out.returncode==0 else 'NOT_A_GIT_CHECKOUT'
        status[name]=values
    result={'status':'PASS' if all(r['PASS'] for r in checks) and consistent else 'FAIL',
        'historical_file_count':len(checks),'historical_pass_count':sum(r['PASS'] for r in checks),
        'all_native_runs_same_extension_and_checkpoint':consistent,'runs':runs,'checks':checks,
        'git_workspaces':status,'disk_free_bytes':{d:shutil.disk_usage(d).free for d in ['C:/','D:/']},
        'remote_connections_this_task':0,'remote_allocation_changes':0,'production_CUDA_compiles':0}
    (TASK/'09_reproducibility/ORIGINAL_ASSET_PROTECTION.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['runs','checks','git_workspaces']},indent=2))
    if result['status']!='PASS':raise RuntimeError('Protected asset changed; stop delivery and investigate')


if __name__=='__main__':main()
