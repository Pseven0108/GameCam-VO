import json,sys
from remote import ROOT,call
mode=sys.argv[1];index=sys.argv[2]
code=r'''
import pathlib,json,os,time,shutil,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');mode=MODE
out=r/'attempts'/mode;log=r/'artifacts'/('STAGE_'+mode)
def read(p,n=3000):return p.read_text(errors='replace')[-n:] if p.is_file() else None
receipts={n:json.loads((out/n).read_text()) for n in ('PROCESS_RECEIPT.json','SUCCESS.json','RESTORE_RECEIPT.json','STAGE_RESUME_INPUT.json') if (out/n).is_file()}
trace=out/'native_trace.jsonl';last=[]
if trace.is_file() and trace.stat().st_size:
 with trace.open('rb') as f:
  size=trace.stat().st_size;f.seek(max(0,size-24000));lines=f.read().decode(errors='replace').splitlines()
 for line in lines[-8:]:
  try:last.append(json.loads(line))
  except Exception:pass
pid=json.loads((log/'STARTED.json').read_text())['wrapper_pid'] if (log/'STARTED.json').is_file() else None
alive=False
if pid:
 try:alive=pathlib.Path('/proc',str(pid),'stat').read_text().split()[2]!='Z'
 except FileNotFoundError:pass
result={'mode':mode,'pid_alive':alive,'receipts':receipts,'trace_bytes':trace.stat().st_size if trace.is_file() else None,'last_events':last,'wrapper_stdout_tail':read(log/'stdout.txt'),'wrapper_stderr_tail':read(log/'stderr.txt'),
 'process_stdout_tail':read(out/'process.stdout.txt',1500),'process_stderr_tail':read(out/'process.stderr.txt',4500),'rerun_bytes':(out/'rerun_stream.rrd').stat().st_size if (out/'rerun_stream.rrd').is_file() else None,'free_bytes':shutil.disk_usage(r).free}
print(json.dumps(result))
'''.replace('MODE',repr(mode))
a=call('R3_POLL_'+mode+'_'+index,code,timeout=90)
(ROOT/'evidence'/('R3_POLL_'+mode+'_'+index+'.json')).write_text(json.dumps(a,indent=2))
if '--compact' in sys.argv:
 report={'mode':a['mode'],'pid_alive':a['pid_alive'],'success':a['receipts'].get('SUCCESS.json'),'process_receipt':a['receipts'].get('PROCESS_RECEIPT.json'),'trace_bytes':a['trace_bytes'],'last_events':[{'kind':x.get('kind'),'rgb':x.get('rgb')} for x in a['last_events']],'rerun_bytes':a['rerun_bytes'],'free_GiB':a['free_bytes']/2**30}
 if not a['pid_alive'] and not report['success']:report.update(stderr=a['process_stderr_tail'],wrapper_error=a['wrapper_stderr_tail'])
 print(json.dumps(report,ensure_ascii=False,indent=2))
else:print(json.dumps(a,ensure_ascii=False,indent=2))
