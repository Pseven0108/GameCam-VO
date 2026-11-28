"""Bounded serial scheduling; stop on any error and never retry a completed run."""
import datetime,hashlib,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
PY=sys.executable
plan=['BASE','A5','ROBUST','ROBUST_A5']
receipt=dict(order=plan,seed=43,attempts=[],remote_connections=0,automatic_retries=False,
    protocol_sha256=hashlib.sha256((TASK/'configs/PROTOCOL.json').read_bytes()).hexdigest())
target=TASK/'reports/SCHEDULE_RECEIPT.json'
if target.exists():raise FileExistsError(target)
def save():target.write_text(json.dumps(receipt,indent=2)+'\n')
save()
for arm in plan:
    row=dict(arm=arm,attempt='001',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='STARTED')
    receipt['attempts'].append(row);save()
    log=TASK/'reports'/f'RUN_{arm}_001.log'
    if log.exists():raise FileExistsError(log)
    print('START',arm,flush=True)
    with log.open('w') as f:
        code=subprocess.call([PY,str(TASK/'scripts/run_wsl.py'),'run_arm.py','--arm',arm,'--attempt','001'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    row.update(exit_code=code,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='COMPLETE' if code==0 else 'FAILED')
    save()
    if code!=0:raise SystemExit(code)
    if not (TASK/'outputs'/f'{arm}_001/COMPLETE.json').exists():raise RuntimeError('Missing full trajectory completion receipt')
    print('COMPLETE',arm,flush=True)
receipt['status']='ALL_FOUR_COMPLETED';save()
