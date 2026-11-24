from transport import *
code=r'''import sys,pathlib,json,os
s=json.loads(sys.stdin.readline());root=pathlib.Path(s['root']);out=[]
for seed in (44,45):
 for arm in json.loads((root/'release/AUTHORIZATION.json').read_text())['orders'][str(seed)]:
  d=root/'results'/('seed'+str(seed))/arm;r=dict(seed=seed,arm=arm,status='NOT_STARTED')
  if (d/'COMPLETE.json').exists():r.update(json.loads((d/'COMPLETE.json').read_text()))
  elif d.exists():
   r['status']='RUNNING';ats=list(d.glob('attempt_*'))
   if ats:
    a=ats[0];r['attempt']=str(a)
    for name in ('progress.json','PROCESS_RECEIPT.json'):
     if (a/name).exists():
      try:r[name]=json.loads((a/name).read_text())
      except json.JSONDecodeError:pass
    if (a/'process.stderr.txt').exists():r['stderr_tail']=(a/'process.stderr.txt').read_text(errors='replace')[-1200:]
  out.append(r)
stop=json.loads((root/'evidence/CAMPAIGN_STOP.json').read_text()) if (root/'evidence/CAMPAIGN_STOP.json').exists() else None
print(json.dumps(dict(runs=out,stop=stop,complete=(root/'evidence/ALL_SIXTEEN_COMPLETE.json').exists(),controller_tail=(root/'evidence/controller.stdout.txt').read_text(errors='replace')[-3000:],controller_stderr=(root/'evidence/controller.stderr.txt').read_text(errors='replace')[-3000:])))
'''
name='status_'+datetime.now(timezone.utc).strftime('%H%M%S%f')
d=rpc(code,dict(root=REMOTE),name)
print(json.dumps(d,ensure_ascii=False))
