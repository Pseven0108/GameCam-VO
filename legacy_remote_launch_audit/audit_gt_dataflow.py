"""CPU-only source-backed GT isolation audit; no real image decoding or pose reads."""
import ast,hashlib,json,os,pathlib,sys,traceback
from launch_contract import AUDIT,ROOT,PREFLIGHT,REFERENCE,FUTURE_ROOT,load
from linux_safety import atomic_json

def main():
    os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    attempted=[]
    def audit(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            p=pathlib.Path(os.fsdecode(args[0]));low=str(p).lower()
            if p.suffix.lower() in {'.pth','.pt','.safetensors','.png','.jpg','.jpeg','.exr','.npy','.npz'} or '/evaluation/' in low or '/gt/' in low:
                attempted.append({'event':event,'path':str(p)});raise RuntimeError('CPU_GT_AUDIT_FORBIDDEN_DATA_READ:'+str(p))
        if event in {'socket.connect','socket.getaddrinfo'}:attempted.append({'event':event});raise RuntimeError('CPU_GT_AUDIT_NETWORK_FORBIDDEN')
    sys.addaudithook(audit)
    repo=ROOT/'baselines/droid_w/upstream';sys.path.insert(0,str(repo))
    import torch
    torch.set_num_threads(2)
    def forbidden(*a,**k):raise RuntimeError('CHECKPOINT_DESERIALIZATION_FORBIDDEN_IN_LAUNCH_AUDIT')
    torch.load=forbidden
    import src.utils.datasets as module
    cfg=load(PREFLIGHT/'GPU_09_120frame_effective_config.json')
    fake_folder=AUDIT/'CPU_fixtures/no_real_images'
    original_glob=module.glob.glob
    globs=[]
    def fake_glob(pattern):
        globs.append(pattern)
        if pattern==str(fake_folder)+'/rgb/frame*.png':return [str(fake_folder/'rgb'/('frame%06d.png'%(7953+i))) for i in range(300)]
        if pattern==str(fake_folder)+'/frame*.jpg':return []
        raise RuntimeError('Unexpected loader filesystem lookup: '+pattern)
    module.glob.glob=fake_glob
    saves=[]
    def forbidden_save(*a,**k):saves.append('save_gt_poses');raise RuntimeError('GT_SAVE_CALLED_IN_RGB_NOPOSE')
    module.BaseDataset.save_gt_poses=forbidden_save
    tests=[]
    try:
        for flag in [True,False]:
            test_cfg=json.loads(json.dumps(cfg));test_cfg['data']['input_folder']=str(fake_folder);test_cfg['save_gt_poses']=flag
            dataset=module.get_dataset(test_cfg,device='cpu')
            # Replace only image decoding with a synthetic CPU tensor. Real constructor, dispatch,
            # BaseDataset.__getitem__ and None-depth/None-pose handling are exercised unchanged.
            dataset.get_color=lambda index:torch.zeros((1,3,288,512),device='cpu')
            idx,image,depth,pose=dataset[0]
            passed=type(dataset) is module.RGB_NoPose and len(dataset)==120 and dataset.poses is None and dataset.depth_paths is None and pose is None and image.device.type=='cpu' and not torch.cuda.is_initialized()
            tests.append({'save_gt_poses_flag':flag,'actual_loader_class':type(dataset).__name__,'length':len(dataset),'poses_is_None':dataset.poses is None,'depth_paths_is_None':dataset.depth_paths is None,'returned_pose_is_None':pose is None,'synthetic_image_shape':list(image.shape),'synthetic_image_device':str(image.device),'depth_shape':list(depth.shape),'CUDA_initialized':torch.cuda.is_initialized(),'real_image_decode_replaced_in_fixture_only':True,'frozen_configuration_modified':False,'passed':passed})
    finally:module.glob.glob=original_glob
    from model_io_boundary import ModelIOBoundary
    spec=load(REFERENCE/'config/dependency_pins.json');case=load(REFERENCE/'config/cases.json')[0]
    policy=ModelIOBoundary(spec,case,cfg['data']['output'],AUDIT/'hypothetical_future_session')
    boundary_tests=[]
    paths=[('allowed_RGB',case['frames'][0]['path_linux'],False,True),('reject_K4_pose_file',str(pathlib.Path(cfg['data']['input_folder'])/'poses.txt'),False,False),('reject_old_evaluation_GT',str(REFERENCE/'evaluation/GT_reference_trajectory.csv'),False,False),('reject_skeleton',str(ROOT/'data/wildworld/Skeleton.json'),False,False),('reject_NPC_state',str(ROOT/'data/wildworld/NPC_State.json'),False,False),('reject_GT_write',str(ROOT/'data/wildworld/gt.txt'),True,False),('allow_generated_prior',cfg['data']['output']+'/mono_priors/features/00000.npy',True,True)]
    for name,path,writing,expected in paths:
        reason=None
        try:allowed=policy.check_path(path,writing)
        except RuntimeError as exc:allowed=False;reason=str(exc)
        boundary_tests.append({'name':name,'path_only_policy_test_no_file_open':True,'writing':writing,'expected_allow':expected,'actual_allow':allowed,'reason':reason,'passed':allowed==expected})
    sources=[]
    selections={
      'configs/droid_w.yaml':[(1,14)],'run.py':[(26,65)],'src/utils/datasets.py':[(65,80),(202,243),(317,341),(453,483),(589,602)],
      'src/tracker.py':[(42,111),(112,174)],'src/motion_filter.py':[(36,113)],'src/frontend.py':[(32,80),(110,150)],
      'src/depth_video.py':[(332,425)],'src/factor_graph.py':[(236,297)],'src/utils/mono_priors/metric_depth_estimators.py':[(20,150)],
      'src/utils/mono_priors/img_feature_extractors.py':[(18,160)],'src/slam.py':[(145,229)],'src/utils/eval_traj.py':[(18,53)]}
    for rel,ranges in selections.items():
        p=repo/rel;raw=p.read_bytes();lines=raw.decode().splitlines()
        sources.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'excerpts':[{'start':a,'end':min(b,len(lines)),'text':'\n'.join(lines[a-1:min(b,len(lines))])} for a,b in ranges]})
    ast_tree=ast.parse((repo/'src/utils/datasets.py').read_text());rgb=next(n for n in ast_tree.body if isinstance(n,ast.ClassDef) and n.name=='RGB_NoPose')
    selected_mentions=[n for n in ast.walk(rgb) if isinstance(n,ast.Constant) and n.value=='save_gt_poses']
    selected_loads=[n for n in ast.walk(rgb) if isinstance(n,ast.Attribute) and n.attr in {'load_poses','save_gt_poses','poses_gt','gt_poses'}]
    assert not selected_mentions and not selected_loads,'Selected loader unexpectedly handles GT'
    atom={'selected_loader_AST_save_flag_reads':len(selected_mentions),'selected_loader_AST_pose_IO_calls':len(selected_loads),'dataset_dispatch_selected':'youtube -> RGB_NoPose','BaseDataset_initial_poses':None,'Tracker_run_tuple_unpack':'timestamp, image, _, _ = stream[i]','Tracker_debug_evaluation_enabled_by_frozen_config':cfg['debug'],'bounded_adapter_calls_SLAM_run_or_terminate':False,'full_trajectory_filler_enabled':False,'GT_evaluation_policy':'Only a separate future CPU evaluator after all model processes exit; no evaluator runs in this audit'}
    result={'selected_configuration_sha256':'70b2527e0293d695c77cdbca1ee4045d75b6483ff262fadd6b0da3749b68cfe9','save_gt_poses':cfg['save_gt_poses'],'source_facts':atom,'actual_CPU_loader_tests':tests,'GT_save_call_attempts':saves,'forbidden_actual_data_or_network_open_attempts':attempted,'model_IO_boundary_policy_tests':boundary_tests,'source_evidence':sources,'real_WildWorld_images_read_or_decoded_in_dynamic_test':False,'synthetic_CPU_tensor_only':True,'torch_imported_for_CPU_loader':True,'CUDA_initialized':torch.cuda.is_initialized(),'model_constructed':False,'model_attempts':0,'checkpoint_deserialized':False,'GT_values_read':False,'new_candidate_config_required':False,'passed':all(x['passed'] for x in tests) and all(x['passed'] for x in boundary_tests) and not attempted and not saves and not torch.cuda.is_initialized()}
    atomic_json(AUDIT/'02_GT_isolation_verification.json',result)
    print(json.dumps({'GT_isolation_passed':result['passed'],'actual_CPU_loader_tests':len(tests),'boundary_policy_tests':len(boundary_tests),'CUDA_initialized':False,'model_attempts':0}),flush=True)
    return 0 if result['passed'] else 2
if __name__=='__main__':raise SystemExit(main())