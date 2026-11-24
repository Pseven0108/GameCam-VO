import json
from remote_cpu import ROOT,call
s=(ROOT/'tools/cpu_closure_roundtrip.py').read_text(encoding='utf-8')
s=s.replace("OUT=ROOT/'cpu_tests/closure_roundtrip_r1'","OUT=ROOT/'cpu_tests/complete_object_diagnostic_r1_fixture16'")
s=s.replace('torch.zeros(1,1,128,8,8)','torch.zeros(1,1,128,16,16)')
a=s.index(" graph=ObjectEncoder();graph.encode(models)")
b=s.index(" print('BUILD_CPU_RUNTIME_BUFFER500',flush=True)")
s=s[:a]+''' report={'unsupported':[],'status':'DIAGNOSTIC_ONLY'}
 class AuditEncoder(ObjectEncoder):
  def encode(self,x):
   try:return super().encode(x)
   except ControlError as ex:
    report['unsupported'].append({'type':str(type(x)),'reason':str(ex)})
    return {'$diagnostic_unsupported':str(type(x))}
 print('AUDIT_MODELS_CONTINUE_ALL_UNSUPPORTED',flush=True)
 enc=AuditEncoder();enc.encode(models)
 report['model_nodes']=len(enc.nodes)
 (OUT/'PARTIAL_AUDIT.json').write_text(json.dumps(report,indent=2))
'''+s[b:]
s=s.replace("cfg['device']='cpu';cfg['data']['output']=str(OUT)","cfg['device']='cpu';cfg['data']['output']=str(OUT)\n os.environ['GAMECAM_TASK003_OBSERVER_JSONL']=str(OUT/'observer.jsonl')")
s=s.replace("runtime=ObjectEncoder(services=services)","services['observer_file']=getattr(roots['observer'],'_file',None)\n runtime=AuditEncoder(services=services)")
s=s.replace("report['status']='PASS'","report['status']='DIAGNOSTIC_NOT_A_RELEASE'")
s=s.replace("report['CPU_snapshot", "report['UNUSED_CPU_snapshot")
code=r'''
import pathlib,sys,os,subprocess,json
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1');p=r/'operational/complete_object_diagnostic.py';p.write_bytes(sys.stdin.buffer.read())
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONHASHSEED='43',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MPLBACKEND='Agg')
with (r/'evidence/CPU_COMPLETE_DIAGNOSTIC_R1_FIXTURE16.stdout.txt').open('xb') as o,(r/'evidence/CPU_COMPLETE_DIAGNOSTIC_R1_FIXTURE16.stderr.txt').open('xb') as e:
 q=subprocess.run(['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python','-B','-u',str(p)],env=env,cwd=r/'source_candidate',stdout=o,stderr=e,timeout=900)
receipt={'exit_code':q.returncode,'stdout_tail':(r/'evidence/CPU_COMPLETE_DIAGNOSTIC_R1_FIXTURE16.stdout.txt').read_text()[-2500:],'stderr_tail':(r/'evidence/CPU_COMPLETE_DIAGNOSTIC_R1_FIXTURE16.stderr.txt').read_text()[-5000:]}
(r/'evidence/CPU_COMPLETE_DIAGNOSTIC_R1_FIXTURE16_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
print(call('CPU_COMPLETE_OBJECT_DIAGNOSTIC_R1_FIXTURE16',code,input_bytes=s.encode(),timeout=950))
