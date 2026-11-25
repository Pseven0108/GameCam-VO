"""Verify all archived R2 runtime members and the R3 initial protection set."""
import pathlib,json
from local_remote import run,ROOT
R2=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1'
initial=json.loads((ROOT/'00_intake/R3_INITIAL_RESOURCE_PROBE.stdout.txt').read_text())
expected={p:v['sha256'] for p,v in initial['files'].items()}
for name in ['plain','trace','final','binary']:
    proof=json.loads((R2/'00_intake'/(name+'_TRANSFER_VERIFICATION.json')).read_text())
    for relative,v in proof['members'].items():expected['/root/rivermind-data/'+R2.name+'/'+relative]=v['sha256']
script='''import pathlib,hashlib,json,subprocess,shutil
expected=EXPECTED
records=[]
for name,want in expected.items():
 p=pathlib.Path(name);h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 records.append({'path':name,'SHA_matches':h.hexdigest()==want,'sha256':h.hexdigest(),'bytes':p.stat().st_size})
def cmd(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=30)
 return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1')
files=[p for p in r.rglob('*') if p.is_file()]
result={'protected_files':records,'all_protected_SHA_unchanged':all(v['SHA_matches'] for v in records),'disk':dict(zip(('total','used','free'),shutil.disk_usage(r))),'r3_total_bytes':sum(p.stat().st_size for p in files),'gpu':cmd(['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader']),'gpu_compute_processes':cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader']),'historical_candidate_status':cmd(['git','-C','/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE/source_candidate','status','--porcelain']),'shutdown_performed':False}
print(json.dumps(result,indent=2))
assert result['all_protected_SHA_unchanged']
'''.replace('EXPECTED',repr(expected))
text=run(script.encode(),'FINAL_PROTECTION_AND_RESOURCE_AUDIT',timeout=120)
result=json.loads(text);(ROOT/'ORIGINAL_EVIDENCE_PRESERVATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='protected_files'},indent=2))
