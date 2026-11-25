import pathlib,json,subprocess,time
r=pathlib.Path('/root/rivermind-data/GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1');a=r/'attempts/D1_S1';out={}
for n in ['native_trace.jsonl','observer.jsonl']:
 p=a/n
 if p.exists():
  with p.open('rb') as f:f.seek(max(0,p.stat().st_size-10000));s=f.read().decode(errors='replace')
  out[n]={'bytes':p.stat().st_size,'mtime':p.stat().st_mtime,'tail':s[-5000:]}
for pid in [745,746]:
 p=pathlib.Path('/proc')/str(pid)
 if p.exists():out[str(pid)]={'status':(p/'status').read_text(),'wchan':(p/'wchan').read_text(),'io':(p/'io').read_text()}
print(json.dumps(out))
