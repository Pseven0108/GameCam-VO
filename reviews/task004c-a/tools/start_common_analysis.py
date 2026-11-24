from transport import *
code=r'''
import sys,json,pathlib,subprocess,os,hashlib
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);assert json.loads((r/'analysis/ANALYSIS_PROCESS.json').read_text())['exit_code']==0
q=r/'control/common_support_analysis.py';assert not q.exists();q.write_text(p['source']);compile(q.read_text(),str(q),'exec')
with (r/'analysis/common_support.stdout.txt').open('xb') as so,(r/'analysis/common_support.stderr.txt').open('xb') as se:
 child=subprocess.Popen([p['python'],'-B','-u',str(q),str(r)],cwd=r,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(r/'control'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),start_new_session=True)
print(json.dumps({'pid':child.pid,'analysis_sha256':hashlib.sha256(q.read_bytes()).hexdigest()}))
'''
r=remote(code,{'root':AUTH['remote_root'],'python':AUTH['lock']['python'],'source':(ROOT/'tools/common_support_analysis.py').read_text(encoding='utf8')},'COMMON_ANALYSIS_LAUNCH',45);print(json.dumps(r))
