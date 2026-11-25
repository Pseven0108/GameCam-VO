import pathlib,json,subprocess
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');out={}
for f in ['build/BUILD_COMPLETE.json','build/BUILD_FAILED.json','evidence/build.stdout.txt','evidence/build.stderr.txt']:
 p=r/f
 if p.exists():out[f]=p.read_text()[-7000:]
p=pathlib.Path('/opt/gamecam-viper-fullseq-3090-20261120-061408');out['toolchain_locations']=[str(x) for x in p.glob('**/nvcc') if len(x.parts)<12]
print(json.dumps(out))
