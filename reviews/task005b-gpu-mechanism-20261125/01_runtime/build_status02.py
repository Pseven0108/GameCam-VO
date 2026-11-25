import pathlib,json
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1')
print(json.dumps({n:(r/n).read_text()[-5000:] for n in ['build_attempt02/BUILD_COMPLETE.json','build_attempt02/BUILD_FAILED.json','evidence/build02.stdout.txt','evidence/build02.stderr.txt'] if (r/n).exists()}))
