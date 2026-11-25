import pathlib,json,subprocess,shutil
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_R3_REDUCTION_U_ISOLATION_20261125_R1')
out={'disk_free':shutil.disk_usage(r).free}
for phase in ['build','run']:
    e=r/'evidence'/phase
    if e.exists():
        out[phase]={p.name:p.read_text()[-3000:] for p in e.iterdir() if p.is_file() and not (phase=='build' and p.suffix=='.txt' and (r/'build/BUILD_COMPLETE.json').exists())}
out['build_complete']=(r/'build/BUILD_COMPLETE.json').read_text() if (r/'build/BUILD_COMPLETE.json').exists() else None
out['build_failed']=(r/'build/BUILD_FAILED.json').read_text() if (r/'build/BUILD_FAILED.json').exists() else None
out['run_complete']=(r/'results/COMPLETE.json').read_text() if (r/'results/COMPLETE.json').exists() else None
print(json.dumps(out,indent=2))
