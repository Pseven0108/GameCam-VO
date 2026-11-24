"""Load only the reviewed output-lifecycle diff, retaining original source files."""
import ast,hashlib,importlib.abc,importlib.util,json,os,pathlib,subprocess,sys
BASE='5d357c1d3079de134dd8b41a20a00632da37f0b0'
TREE='c018a65009aaf4f7457e2da5225a5f322a168b77'
REPLACEMENTS=(
 ('    # Resolve frozen prior classes without rerunning either prior model.',
  '    cached_priors();install_lossless_video_io()\n    # Resolve frozen prior classes without rerunning either prior model.'),
 ('printer=RestoreIOPrinter(ctx);event_writer=SummaryWriter(str(out/\'native\'))',
  'printer=RestoreIOPrinter(ctx);event_writer=prepare_summary_writer(out,SummaryWriter)'),
 ('    pathlib.Path(tracker.output).mkdir(parents=True,exist_ok=False)',
  '    validate_rebound_output(bundle,out)'),
)

def transformed(raw):
    text=raw.decode('utf-8')
    for old,new in REPLACEMENTS:
        if text.count(old)!=1:raise RuntimeError('I/O overlay source anchor differs')
        text=text.replace(old,new)
    insert='from gamecam_io_overlay import prepare_summary_writer,validate_rebound_output\nfrom runtime_io import install_lossless_video_io\n'
    anchor='from run import setup_seed\n'
    if text.count(anchor)!=1:raise RuntimeError('I/O import anchor differs')
    text=text.replace(anchor,anchor+insert)
    before=ast.parse(raw);after=ast.parse(text)
    bf={n.name:ast.dump(n,include_attributes=False) for n in before.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    af={n.name:ast.dump(n,include_attributes=False) for n in after.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    if set(bf)!=set(af) or [k for k in bf if bf[k]!=af[k]]!=['restore_and_continue']:
        raise RuntimeError('Overlay changed a captured class or non-I/O entry')
    return text

class Loader(importlib.abc.Loader):
    def __init__(self,path):self.path=path
    def create_module(self,spec):return None
    def exec_module(self,module):
        raw=self.path.read_bytes();changed=transformed(raw)
        module.__file__=str(self.path)
        exec(compile(changed,str(self.path),'exec'),module.__dict__)
        out=os.environ.get('GAMECAM_NATIVE_ATTEMPT')
        if out:
            p=pathlib.Path(out)/('IO_OVERLAY_LOADED_'+str(os.getpid())+'.json')
            with p.open('x') as f:json.dump({'base_commit':BASE,'base_tree':TREE,'source_sha256':hashlib.sha256(raw).hexdigest(),'effective_driver_sha256':hashlib.sha256(changed.encode()).hexdigest(),'pid':os.getpid(),'source_on_disk_unchanged':True,'only_output_lifecycle':False,'scope':'OUTPUT_LIFECYCLE_LOCAL_HUB_LOSSLESS_VIDEO_AND_TMPFS_MMAP'},f,indent=2)
class Finder(importlib.abc.MetaPathFinder):
    def __init__(self,path):self.path=path
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='native_control.native_driver':return importlib.util.spec_from_file_location(fullname,self.path,loader=Loader(self.path))

def install(root):
    root=pathlib.Path(root);source=root/'source_candidate'
    def git(*a):return subprocess.check_output(['git','-C',str(source),*a],text=True).strip()
    if git('rev-parse','HEAD')!=BASE or git('rev-parse','HEAD^{tree}')!=TREE or git('status','--porcelain','--untracked-files=all'):
        raise RuntimeError('Original source pin/worktree changed')
    manifest=json.loads((root/'overlay/OVERLAY_MANIFEST.json').read_text())
    for name,sha in manifest['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Overlay SHA mismatch '+name)
    driver=source/'native_control/native_driver.py'
    if hashlib.sha256(driver.read_bytes()).hexdigest()!=manifest['base_driver_sha256']:raise RuntimeError('Original driver SHA differs')
    transformed(driver.read_bytes())
    sys.path.insert(0,str(root/'overlay'));sys.meta_path.insert(0,Finder(driver))
    from runtime_io import configure_tmpfs_arena,install_resource_accounting
    install_resource_accounting(root)
    if os.environ.get('GAMECAM_NATIVE_ATTEMPT'):configure_tmpfs_arena(root)

