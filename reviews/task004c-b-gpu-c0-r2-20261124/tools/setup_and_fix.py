"""Clone the reviewed source and change only NativeViperRGB's input contract."""
import json,pathlib,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'DROID_W_TASK004C_B_GPU_C0_20261124_R1'
# The already pinned transport is copied as a task-local helper; it opens no connection on import.
shutil.copyfile(OLD/'tools/remote_cpu.py',ROOT/'tools/remote_cpu.py')
sys.path.insert(0,str(ROOT/'tools'))
from remote_cpu import call
protocol=ROOT.parent/'DROID_W_TASK004C_B_PROTOCOL_20261123T170327098Z'/'TASK004C_B_COMMON_CHECKPOINT_MANIFEST.json'
schema=json.loads(protocol.read_text('utf-8'));assert len(schema['tensors'])==47
(ROOT/'evidence').mkdir(exist_ok=True)
(ROOT/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').write_bytes(protocol.read_bytes())
code=r'''
import hashlib,json,pathlib,shutil,subprocess
origin=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1')
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
source=origin/'source_candidate';base='668a88c74c7f7a88a572679d2bd8e86c0a05514b'
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==base
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'])
root.mkdir(exist_ok=False)
for name in ['evidence','artifacts','attempts','operational','cpu_tests']:(root/name).mkdir()
q=subprocess.run(['git','clone','--no-hardlinks','--local',str(source),str(root/'source_candidate')],capture_output=True,text=True,timeout=60);assert q.returncode==0
src=root/'source_candidate'
subprocess.run(['git','-C',str(src),'switch','-c','codex/task004c-b-rgb-contract-fix-r2'],check=True,capture_output=True)
for name in ['native_control','checkpoint','schedule','runner','control_common.py','tests']:
 (root/name).symlink_to(src/name,target_is_directory=(src/name).is_dir())
shutil.copytree(origin/'configs',root/'configs')
shutil.copyfile(origin/'evidence/FILE_BACKED_CPU_VALIDATION.json',root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
for name in ['CPU_TEST_REPORT.json']:
 shutil.copyfile(origin/'artifacts/RELEASE_CPU_final'/name,root/'evidence/PRIOR_152_CPU_TEST_REPORT.json')
target=src/'native_control/dataset.py';before=target.read_bytes();old=before.decode()
assert hashlib.sha256(before).hexdigest()=='dcb87c7294a71ddaa772545ba3b38ce9402dfd47031357a57a3ef315972a8d12'
needle="""        row=self.frames[index];p=Path(self.color_paths[index])
        expected=row.get('sha256',row.get('rgb_sha256'))
        if expected and file_sha(p)!=expected:raise ControlError('RGB content changed')
        item=super().__getitem__(index);ts,color,depth,pose=item
        if ts!=index or pose is not None or depth is not None or tuple(color.shape)!=(1,3,360,640):raise ControlError('R2 RGB-only input contract mismatch')
"""
replacement="""        # Reject label sources before the parent loader can read them.
        if self.depth_paths is not None or self.poses is not None:
            raise ControlError('RGB-only stream contains an unexpected label source')
        row=self.frames[index];p=Path(self.color_paths[index])
        if type(row.get('rgb_id')) is not int or row['rgb_id']!=index+1:
            raise ControlError('RGB frame ID does not match the frozen cursor')
        expected=row.get('sha256',row.get('rgb_sha256'))
        if expected and file_sha(p)!=expected:raise ControlError('RGB content changed')
        item=super().__getitem__(index);ts,color,depth,pose=item
        if (type(ts) is not int or ts!=index or pose is not None
                or not isinstance(color,torch.Tensor) or tuple(color.shape)!=(1,3,360,640)):
            raise ControlError('R2 RGB-only input contract mismatch')
        # BaseDataset uses this exact zero Tensor to represent absent depth.
        # Keep the original tuple and reject None, labels, NaN/Inf and other layouts.
        if (not isinstance(depth,torch.Tensor) or depth.dtype!=torch.float32
                or depth.device.type!='cpu' or tuple(depth.shape)!=tuple(color.shape[-2:])
                or depth.layout!=torch.strided or bool(torch.count_nonzero(depth))):
            raise ControlError('Invalid RGB-only zero-depth placeholder')
"""
assert old.count(needle)==1
target.write_text(old.replace(needle,replacement))
(root/'evidence/NativeViperRGB.before.py').write_bytes(before)
(root/'evidence/NativeViperRGB.after.py').write_bytes(target.read_bytes())
diff=subprocess.check_output(['git','-C',str(src),'diff','--','native_control/dataset.py'])
(root/'evidence/RGB_CONTRACT_FIX.patch').write_bytes(diff)
assert subprocess.check_output(['git','-C',str(src),'diff','--name-only'],text=True).splitlines()==['native_control/dataset.py']
subprocess.run(['git','-C',str(src),'add','--','native_control/dataset.py'],check=True,capture_output=True)
subprocess.run(['git','-C',str(src),'commit','-m','Accept only the verified zero-depth CPU placeholder in NativeViperRGB'],check=True,capture_output=True)
commit=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
assert subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD^'],text=True).strip()==base
result={'root':str(root),'source_commit':commit,'parent_commit':base,'parent_of_parent':'0931141cf88247dc8fb0c7628c1d91b6531fea90',
 'changed_runtime_files':['native_control/dataset.py'],'before_sha256':hashlib.sha256(before).hexdigest(),
 'after_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'old_candidate_modified':False,
 'GPU_runs':0,'None_depth_policy':'REJECT under the user-specified strict Tensor-only contract; actual parent returns zeros',
 'CPU_environment_only':True}
(root/'evidence/SOURCE_PROVENANCE.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
'''
d=json.loads(call('SETUP_DATASET_FIX',code,timeout=120))
(ROOT/'evidence/SOURCE_PROVENANCE.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d))
