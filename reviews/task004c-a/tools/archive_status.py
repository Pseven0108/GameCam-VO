from transport import *
code=r'''
import sys,json,pathlib,base64,shutil
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['root']);out={'free_bytes':shutil.disk_usage(r).free}
for name in ['RAW_ARCHIVE_STATUS.json','RAW_SHA256_MANIFEST.json','archive.stdout.txt','archive.stderr.txt']:
 q=r/'archives'/name
 if q.is_file():out[name]=q.read_text()
print(json.dumps(out))
'''
r=remote(code,{'root':AUTH['remote_root']},'ARCHIVE_STATUS_'+str(time.time_ns()),60)
for name,text in r.items():
 if isinstance(text,str):(ROOT/'evidence'/name).write_text(text,encoding='utf8')
x=json.loads(r.get('RAW_ARCHIVE_STATUS.json','{}'));print(json.dumps(x,indent=2))
