"""Read-only RGB/config validation with a fake tracker. No model or GT imports."""
import argparse,csv,hashlib,io,json,os,pathlib,sys,time
from runtime_dependency_pins import RuntimePins,digest_file,require
from model_io_boundary_v2 import ModelIOBoundary

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);p.add_argument('--planned-model-output',required=True);a=p.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU_MODE_REQUIRED')
    root=pathlib.Path(a.root).resolve();output=pathlib.Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
    pins=RuntimePins(root);static=pins.static_check();original_hash=digest_file(pins.spec['config']['real_linux'])
    cfg=pins.effective_config(a.planned_model_output)
    actual={'max_frames':cfg['max_frames'],'stride':cfg['stride'],'buffer':cfg['tracking']['buffer'],'warmup':cfg['tracking']['warmup'],'motion_filter':cfg['tracking']['motion_filter']['thresh'],'mapping':cfg['mapping']['enable']}
    expected={'max_frames':120,'stride':1,'buffer':350,'warmup':12,'motion_filter':3.0,'mapping':False};require(actual==expected,'EFFECTIVE_CONFIGURATION_CONFLICT')
    comparisons=json.loads(json.dumps(cfg));comparisons['max_frames']=pins._checked_original['max_frames'];comparisons['data']['output']=pins._checked_original['data']['output'];require(comparisons==pins._checked_original,'UNAPPROVED_CONFIG_MUTATION')
    config_path=output/'effective_config_120.json';config_path.write_text(json.dumps(cfg,indent=2)+'\n')
    def emit(name,data):(output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    emit('static_runtime_validation.json',static)
    emit('effective_config_test_report.json',{'status':'PASS','effective_config_called':True,'actual_fields':actual,'only_changes':['max_frames:60->120','data.output:isolated planned output'],'original_config_sha256':original_hash,'original_config_unchanged':digest_file(pins.spec['config']['real_linux'])==original_hash,'generated_config_path':str(config_path),'generated_config_sha256':digest_file(config_path),'planned_output_created':pathlib.Path(a.planned_model_output).exists(),'checkpoint_deserialized':False})
    import cv2,numpy as np
    cv2.setNumThreads(2)
    rows=list(csv.DictReader(io.StringIO(pins._frozen_files['k4_input_frames.csv'].decode('utf-8-sig'))));case=json.loads(pins._frozen_files['cases.json'].decode('utf-8-sig'))[0]
    boundary=ModelIOBoundary([f['path_linux'] for f in case['frames']],[],[pathlib.Path(pins.spec['k4_live_contract']['real_linux']).parents[6]], [output])
    results=[];raw_hashes=set();decoded_hashes=set();native_ordinals=[];start=time.monotonic()
    for i,(row,f) in enumerate(zip(rows,case['frames'])):
        path=pathlib.Path(f['path_linux']);boundary.check_path(path)
        raw=path.read_bytes();h=hashlib.sha256(raw).hexdigest();image=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
        require(image is not None,'RGB_DECODE_FAILED:'+str(path));decoded=hashlib.sha256(image.tobytes()).hexdigest()
        require(h==row['png_sha256']==f['png_sha256'] and decoded==row['decoded_bgr_sha256']==f['decoded_bgr_sha256'],'RGB_HASH_MISMATCH:'+str(path))
        require(image.shape==(288,512,3) and image.dtype==np.uint8,'IMAGE_SHAPE_OR_DTYPE')
        require(i==int(row['ordinal']) and int(row['published_frame_index'])==7953+i and path.name==f'frame{7953+i:06d}.png','FRAME_ORDER_OR_INDEX_CONFLICT')
        rgb=image[:,:,::-1].astype(np.float32)/255.;require(np.array_equal((rgb*255).round().astype(np.uint8)[:,:,::-1],image),'BGR_RGB_CONVERSION')
        # FakeTracker consumes only ordinal, RGB and fixed K; it produces no pose.
        packet={'ordinal':i,'rgb_shape':[1,3,288,512],'K':case['K4'],'pose':None,'depth':None}
        require(set(packet)=={'ordinal','rgb_shape','K','pose','depth'} and packet['pose'] is None and packet['depth'] is None,'MODEL_PACKET_BOUNDARY')
        native_ordinals.append(i);raw_hashes.add(h);decoded_hashes.add(decoded)
        results.append({'ordinal':i,'published_frame':7953+i,'path':str(path),'realpath':str(path.resolve()),'png_sha256':h,'decoded_bgr_sha256':decoded,'width':512,'height':288,'dtype':'uint8','input_channel_order':'BGR (OpenCV)','model_channel_order':'RGB float32 [0,1]','native_time_index':i,'passed':True})
    require(len(results)==120,'FRAME_COUNT');require(len(raw_hashes)==len(decoded_hashes)==120,'DUPLICATE_RGB_CONTENT')
    reject_results=[]
    for name in ['state.csv','skeleton.npz','camera_pose.csv','NPC.csv','Monster.csv']:
        try:boundary.check_path(path.parent/name)
        except RuntimeError as e:reject_results.append({'name':name,'rejected':True,'reason':str(e)})
        else:raise RuntimeError('GT_OR_ANALYSIS_PATH_ALLOWED:'+name)
    emit('rgb_decode_report.json',{'status':'PASS','frames_expected':120,'frames_decoded':120,'decode_success_rate':1.0,'raw_hash_unique_count':len(raw_hashes),'decoded_hash_unique_count':len(decoded_hashes),'checks':results,'seconds':time.monotonic()-start,'cv2_version':cv2.__version__,'numpy_version':np.__version__,'model_loaded':False,'GT_values_read':False})
    emit('input_integrity_report.json',{'status':'PASS','sequence':'V56_01','window':'middle','published_frames':[7953,8072],'frames':120,'stride':1,'missing':[],'duplicate_paths':[],'duplicate_raw_hashes':0,'native_indices':native_ordinals,'time_semantics':'0-based stream ordinals; no physical timestamps are supplied by this frozen PNG manifest, and no FPS is inferred.','configuration_sha256':digest_file(config_path),'input_manifest_sha256':digest_file(root/'config/k4_input_frames.csv'),'GT_values_read':False})
    emit('gt_isolation_report.json',{'status':'PASS','real_reads':'120 frozen RGB PNG files plus pinned configurations/manifests and checkpoint raw hashes only','model_packet_fields':['ordinal','rgb_shape','K','pose=None','depth=None'],'analysis_data_rejections':reject_results,'GT_values_read':False,'GT_pose_evaluation_executed':False,'boundary_limit':'Python allowlist and audited fixed native call graph; not a native-code OS sandbox.'})
    emit('cpu_pipeline_e2e.json',{'status':'PASS','fake_tracker_frames':120,'native_tracker_called':False,'pose_estimation_executed':False,'checkpoint_deserialized':False,'torch_imported':'torch' in sys.modules,'CUDA_initialized':False,'NVML_called':False,'GT_values_read':False,'Attempt_02_created':False})
    print(json.dumps({'status':'PASS','decoded_frames':len(results),'unique_png':len(raw_hashes),'generated_config_sha256':digest_file(config_path),'torch_imported':'torch' in sys.modules,'planned_output_created':pathlib.Path(a.planned_model_output).exists()}))
if __name__=='__main__':main()
