from transport import *
import difflib,ast
for name in ('task004_controls.py','task004_run_segment.py'):
 old=(A/'release/candidates'/name).read_text();new=(ROOT/'release/candidates'/name).read_text();ast.parse(new)
 (ROOT/'release'/('B_vs_A_'+name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='Task004A/'+name,tofile='Task004B/'+name)),encoding='utf-8')
print('SEED_AND_AUTHORIZATION_OVERLAY_AST_PASS')
