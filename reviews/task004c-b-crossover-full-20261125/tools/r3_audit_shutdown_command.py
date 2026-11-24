"""Read-only audit of the platform shutdown command; never invokes shutdown."""
import json,pathlib,urllib.request,hashlib,html.parser,time
from remote import ROOT,call
url='https://docs.gpuhome.cc/docs/instance/scheduled-shutdown.html'
class Text(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,x):self.parts.append(x)
try:
 req=urllib.request.Request(url,headers={'User-Agent':'GameCam-VO-authorized-shutdown-audit'})
 with urllib.request.urlopen(req,timeout=30) as r: raw=r.read(1024*1024);status=r.status
 parser=Text();parser.feed(raw.decode('utf-8'));text='\n'.join(x.strip() for x in parser.parts if x.strip())
 (ROOT/'evidence/R3_SHUTDOWN_OFFICIAL_DOCUMENT.txt').write_text(text,encoding='utf-8')
 doc={'url':url,'HTTP_status':status,'bytes':len(raw),'html_sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'shutdown_mentions':[text[max(0,i-130):i+400] for i in [m for m in range(len(text)) if text.startswith('shutdown',m)]]}
except Exception as e:doc={'url':url,'read_error':type(e).__name__+': '+str(e)}
(ROOT/'evidence/R3_SHUTDOWN_DOC_AUDIT.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
code=r'''
import subprocess,pathlib,shutil,json,hashlib,time
p=shutil.which('shutdown');resolved=str(pathlib.Path(p).resolve()) if p else None
q=subprocess.run(['bash','-lc','type -a shutdown'],capture_output=True,text=True)
b=pathlib.Path(resolved).read_bytes() if resolved else b''
try:content=b.decode('utf-8') if len(b)<262144 else None
except UnicodeDecodeError:content=None
print(json.dumps({'unix':time.time(),'resolved_from_PATH':p,'realpath':resolved,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'type_stdout':q.stdout,'type_stderr':q.stderr,'type_exit':q.returncode,'text_source':content,'shutdown_executed':False}))
'''
a=call('R3_SHUTDOWN_COMMAND_READONLY_AUDIT_01',code,timeout=45)
(ROOT/'evidence/R3_SHUTDOWN_COMMAND_AUDIT.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'official_doc':doc,'command':a},ensure_ascii=False,indent=2))
