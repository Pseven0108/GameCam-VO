"""One audited Windows/WSL path protocol; stdlib only, never shell=True."""
import hashlib,json,ntpath,subprocess,time
from pathlib import Path,PurePosixPath
O=Path(__file__).resolve().parents[1]
WSL_PY='/home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python'
CALLS=[];CONVERSIONS=[];_cache={}
class PathConversionError(RuntimeError):
 def __init__(self,message,details=None):
  self.details=details or {};super().__init__(message+' '+json.dumps(self.details,ensure_ascii=False))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def run_wsl(arguments):
 command=['wsl.exe','-d','Ubuntu','--',*map(str,arguments)];entry=dict(command=command,shell=False,started_unix=time.time(),timeout_seconds=15)
 try:
  p=subprocess.run(command,shell=False,capture_output=True,text=True,encoding='utf-8',errors='strict',timeout=15)
  entry.update(stdout=p.stdout,stderr=p.stderr,returncode=p.returncode,finished_unix=time.time());CALLS.append(entry);return entry
 except BaseException as e:
  entry.update(stdout=str(getattr(e,'stdout','') or ''),stderr=str(getattr(e,'stderr','') or ''),returncode=None,error_type=type(e).__name__,error_message=str(e),finished_unix=time.time());CALLS.append(entry);raise PathConversionError('WSL_COMMAND_FAILED',entry) from e
def within_stage(path):
 p=Path(path).resolve();root=O.resolve()
 if not p.is_relative_to(root):raise PathConversionError('WINDOWS_PATH_OUTSIDE_CURRENT_STAGE',dict(path=str(p),stage=str(root)))
 return p
def windows_to_wsl(path,*,inject_failure=False):
 p=within_stage(path);normalized=p.as_posix();key=ntpath.normcase(ntpath.normpath(str(p)))
 if inject_failure:raise PathConversionError('INTENTIONAL_PATH_CONVERSION_ERROR',dict(path=normalized,injected_CPU_test_only=True,actual_conversion_executed=False))
 if key in _cache:return _cache[key]
 forward=run_wsl(['wslpath','-u','-a',normalized])
 if forward['returncode']!=0:raise PathConversionError('PATH_CONVERSION_FAILED',forward)
 linux=forward['stdout'].strip()
 if not linux or '\n' in linux or not PurePosixPath(linux).is_absolute() or '..' in PurePosixPath(linux).parts:raise PathConversionError('INVALID_WSL_ABSOLUTE_PATH',dict(path=linux,call=forward))
 relative=p.relative_to(O).as_posix();root_suffix='/'+O.name
 expected_suffix=root_suffix+('/'+relative if relative!='.' else '')
 if not linux.endswith(expected_suffix):raise PathConversionError('WSL_PATH_NOT_CURRENT_STAGE',dict(actual=linux,required_suffix=expected_suffix))
 reverse=run_wsl(['wslpath','-w',linux]);returned=reverse['stdout'].strip()
 if reverse['returncode']!=0 or ntpath.normcase(ntpath.normpath(returned))!=key:raise PathConversionError('PATH_ROUNDTRIP_MISMATCH',dict(original=str(p),reverse=reverse))
 _cache[key]=linux;CONVERSIONS.append(dict(windows_absolute=str(p),normalized_windows=normalized,wsl_absolute=linux,roundtrip_windows=returned,forward=forward,reverse=reverse,roundtrip_equal=True));return linux
def require_exists(linux_path,kind='directory'):
 result=run_wsl(['test','-d' if kind=='directory' else '-f',linux_path])
 if result['returncode']!=0:raise PathConversionError('WSL_PATH_NOT_FOUND',dict(path=linux_path,kind=kind,call=result))
 return result
def scenario_linux_path(root_linux,root_windows):
 p=within_stage(root_windows);rel=p.relative_to(O);actual=PurePosixPath(root_linux).joinpath(*rel.parts)
 if not actual.is_relative_to(PurePosixPath(root_linux)) or '..' in actual.parts:raise PathConversionError('SCENARIO_PATH_ESCAPE',dict(root=root_linux,path=str(actual)))
 return str(actual)
def pin():
 x=json.loads((O/'config/host_pin.json').read_text(encoding='utf-8-sig'));host=Path(x['pwsh_absolute_path'])
 if not host.is_absolute() or not host.is_file() or sha(host)!=x['pwsh_sha256']:raise RuntimeError('PINNED_POWERSHELL_PATH_OR_HASH_MISMATCH')
 if x['required_version']!='7.6.9' or x['required_edition']!='Core':raise RuntimeError('PINNED_POWERSHELL_VERSION_CONTRACT')
 return x
def monitor_command(root,session,**options):
 within_stage(root);x=pin();command=[x['pwsh_absolute_path'],*x['monitor_arguments'],'-File',str(O/'scripts/windows_monitor.ps1'),'-Root',str(root),'-Session',session]
 for k,v in options.items():
  command.append('-'+k)
  if v is not True:command.append(str(v))
 return command
def wsl_consumer_command(root_linux,scenario_linux,session,purpose):
 return ['wsl.exe','-d','Ubuntu','--',WSL_PY,'-B','-u',root_linux+'/scripts/validate_monitor_cpu.py','--root',scenario_linux,'--session',session,'--purpose',purpose]
