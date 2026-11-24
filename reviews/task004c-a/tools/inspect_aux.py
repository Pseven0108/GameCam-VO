from transport import *
code=r'''
import sys,json,pathlib
p=json.loads(sys.stdin.readline());r={}
for f in ['src/utils/droid_visualization_rerun.py','src/tracker.py','src/frontend.py']:
 r[f]=(pathlib.Path(p['lock']['source'])/f).read_text()
print(json.dumps(r))
'''
r=remote(code,AUTH,'AUX_SOURCE_READ',40)
for f,s in r.items():
 q=ROOT/'source'/f;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf8')
print('read',list(r))
