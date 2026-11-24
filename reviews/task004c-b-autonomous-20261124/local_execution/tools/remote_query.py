import sys
from remote_cpu import call
if __name__=='__main__':
 print(call(sys.argv[1],sys.stdin.read(),timeout=240,**({'python':sys.argv[2]} if len(sys.argv)>2 else {})))
