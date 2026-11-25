import pathlib,json,shutil
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1')
out={'disk_free':shutil.disk_usage(r).free,'phases':{}}
for phase in ('plain','build','trace'):
 p=r/'evidence'/phase
 if p.exists():out['phases'][phase]={n:(p/n).read_text()[-5000:] for n in ('stdout.txt','stderr.txt','PROCESS_RECEIPT.json') if (p/n).exists()}
out['calls']=[p.name for p in (r/'results').rglob('*.receipt.json')]
print(json.dumps(out,indent=2))
