import ast,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];C=ROOT/'candidate'
def edit(rel,old,new):
    p=C/rel;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(rel,old);s=s.replace(old,new);ast.parse(s);p.write_text(s,encoding='utf-8',newline='\n')
edit('src/depth_video.py','from native_control.install import selected_flags\n','from native_control.install import selected_flags\nfrom native_control.file_backed import cpu_zeros\n')
edit('src/depth_video.py',"self.images = torch.zeros(buffer, 3, ht, wd, device='cpu', dtype=torch.float32)","self.images = cpu_zeros('images', (buffer, 3, ht, wd), dtype=torch.float32)")
edit('src/depth_video.py',"self.dino_feats = torch.zeros(buffer, ht//self.feature_downsample_factor, wd//self.feature_downsample_factor, n_features, device='cpu', dtype=torch.float).share_memory_()", "self.dino_feats = cpu_zeros('dino_feats', (buffer, ht//self.feature_downsample_factor, wd//self.feature_downsample_factor, n_features), dtype=torch.float, native_share=True)")
edit('native_control/binding.py','from native_control.snapshot import save_state,load_state,state_inventory,ObjectEncoder','from native_control.snapshot import save_state,load_state,state_inventory,ObjectEncoder,prepare_state,save_prepared_state')
edit('native_control/binding.py',"        manifest=save_state(bundle,path,provenance=provenance,services=services)\n        return manifest", "        prepared=prepare_state(bundle,provenance=provenance,services=services,destination_parent=Path(path).parent)\n        budget_file=Path(path).parent/'C0_EXACT_BUDGET_BEFORE_SAVE.json'\n        with budget_file.open('x') as f:json.dump(prepared['budget'],f,indent=2)\n        return save_prepared_state(prepared,path)")
edit('native_control/binding.py',"    bundle,manifest=load_state(path,services=services,expected_sha=expected_sha,allow_cuda=allow_cuda)", "    factory=None\n    arena_root=os.environ.get('GAMECAM_FILE_BACKED_CPU_ROOT')\n    if arena_root:\n        from native_control.file_backed import FileArena\n        arena=FileArena(Path(arena_root));factory=arena.restore_storage\n    bundle,manifest=load_state(path,services=services,expected_sha=expected_sha,allow_cuda=allow_cuda,cpu_storage_factory=factory)")
edit('runner/run_native_smoke.py',"CUDA_VISIBLE_DEVICES='0',TORCH_HOME=data+'/torch_hub'", "CUDA_VISIBLE_DEVICES='0',GAMECAM_FILE_BACKED_CPU_ROOT=str(out/'shared_cpu'),TORCH_HOME=data+'/torch_hub'")
# The single old fixture below did not contain the vanilla cfg safety inputs.
# Preserve its assertion and test identity; retain original source separately.
p=ROOT/'tests/test_native.py';s=p.read_text();old="c=self.ctrl(D=0);set_active(c);v=types.SimpleNamespace(metric_depth_reg=True,uncertainty_aware=True,enable_affine_transform=True,enable_bidirectional_uncer=False)"
assert s.count(old)==1
new=old[:-1]+",cfg={'tracking':{'uncertainty_params':{'gamma_depth':0.01},'frontend':{'enable_loop':False}}})"
s=s.replace(old,new);p.write_text(s,encoding='utf-8',newline='\n')
print('Allocator, exact budgeting and restore factory wired in independent candidate; one legacy fixture supplied missing cfg')
