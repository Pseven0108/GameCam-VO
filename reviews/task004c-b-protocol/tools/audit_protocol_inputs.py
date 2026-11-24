import ast,csv,hashlib,json,math,os,sys,zipfile,time
from pathlib import Path
root=Path(sys.argv[1]); rec=Path(sys.argv[2]); ar=Path(sys.argv[3]); br=Path(sys.argv[4]); cr=rec.parent
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
def dump(name,obj): (root/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
attrs=[]; defs=[]
for f in sorted((root/'source_evidence').rglob('*.py')):
    tree=ast.parse(f.read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            defs.append(dict(file=f.relative_to(root).as_posix(),name=node.name,line=node.lineno,end_line=node.end_lineno))
        if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='self' and isinstance(node.ctx,ast.Store):
            attrs.append(dict(file=f.relative_to(root).as_posix(),name=node.attr,line=node.lineno))
dump('evidence/SOURCE_MUTABLE_ATTRIBUTE_INVENTORY.json',attrs);dump('evidence/SOURCE_FUNCTION_INDEX.json',defs)
records=[]
for base in [ar,br]:
    for z in sorted((base/'raw_archives').glob('*.zip')):
        with zipfile.ZipFile(z) as zz:
            ii=zz.infolist(); totals=sum(i.file_size for i in ii); comp=sum(i.compress_size for i in ii)
            recbytes=sum(i.file_size for i in ii if i.filename.endswith('.rrd'))
            logs=sum(i.file_size for i in ii if i.filename.endswith(('.jsonl','.log','.stdout.txt','.stderr.txt')))
            records.append(dict(archive=str(z),archive_bytes=z.stat().st_size,uncompressed_bytes=totals,compressed_payload_bytes=comp,members=len(ii),rerun_bytes=recbytes,log_bytes=logs))
dump('evidence/HISTORICAL_ARCHIVE_SIZES.json',records)
with (br/'reports/TASK004B_24_RUN_MASTER_TABLE.csv').open(encoding='utf-8-sig',newline='') as f: master=list(csv.DictReader(f))
selected_cols=[k for k in master[0] if any(t in k.lower() for t in ['runtime','elapsed','memory','shm','peak','keyframe','ba_calls']) and 'ids' not in k.lower()]
compact=[{k:r.get(k) for k in ['seed','arm','status']+selected_cols} for r in master]
dump('evidence/HISTORICAL_COST_RECORDS.json',compact)
last=json.loads((rec/'evidence/END_STATE_READONLY.json').read_text());dump('evidence/HISTORICAL_LAST_RESOURCE_MEASUREMENT.json',last)
init=json.loads((cr/'evidence/COMMON_INITIALIZATION_COMPARISON.json').read_text());dump('evidence/HISTORICAL_COMMON_INITIALIZATION_COMPARISON.json',init)
rows=[]
with (cr/'results/TASK004C_B_HISTORICAL_BA_BOUNDARY_GRAPH.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if 'init' in r['stage']: rows.append(r)
dump('evidence/HISTORICAL_INITIALIZATION_BA_BOUNDARIES.json',rows)
B=500;h=360;w=640;hs=45;ws=80;c=384
spec=[('timestamp',[B],4,'CUDA'),('images',[B,3,h,w],4,'CPU'),('dirty',[B],1,'CUDA'),('npc_dirty',[B],1,'CUDA'),('poses',[B,7],4,'CUDA'),('disps',[B,hs,ws],4,'CUDA'),('zeros',[B,hs,ws],4,'CUDA'),('disps_up',[B,h,w],4,'CUDA'),('intrinsics',[B,4],4,'CUDA'),('mono_disps',[B,hs,ws],4,'CUDA'),('mono_disps_up',[B,h,w],4,'CUDA'),('depth_scale',[B],4,'CUDA'),('depth_shift',[B],4,'CUDA'),('valid_depth_mask',[B,h,w],1,'CUDA'),('valid_depth_mask_small',[B,hs,ws],1,'CUDA'),('fmaps',[B,1,128,hs,ws],2,'CUDA'),('nets',[B,128,hs,ws],2,'CUDA'),('inps',[B,128,hs,ws],2,'CUDA'),('dino_feats',[B,25,45,c],4,'CPU'),('dino_feats_resize',[B,c,hs,ws],4,'CUDA'),('uncertainties',[B,hs,ws],4,'CUDA'),('affine_weights',[c+1],4,'CUDA'),('temp_y_cdot',[B,hs,ws],4,'CUDA')]
arr=[dict(name=n,shape=sh,itemsize=s,device=d,bytes=math.prod(sh)*s) for n,sh,s,d in spec]
full=sum(a['bytes'] for a in arr); compact_base=sum((a['bytes']*13//500 if a['shape'][0]==500 else a['bytes']) for a in arr)
# Four levels: 45x80,22x40,11x20,5x10; leading source grid remains45x80.
corr_elements=3600*(3600+22*40+11*20+5*10)
maxout=max(r['uncompressed_bytes'] for r in records);maxarc=max(r['archive_bytes'] for r in records)
metrics={}
for k in selected_cols:
    vals=[]
    for r in master:
        try: vals.append(float(r[k]))
        except (TypeError,ValueError):pass
    if vals:metrics[k]=dict(min=min(vals),max=max(vals),mean=sum(vals)/len(vals),count=len(vals))
resource=dict(video_buffers=arr,full_video_logical_bytes=full,video_cpu_logical_bytes=sum(a['bytes'] for a in arr if a['device']=='CPU'),video_cuda_logical_bytes=sum(a['bytes'] for a in arr if a['device']=='CUDA'),illustrative_13_slot_bytes=compact_base,illustrative_13_slot_conditions='NOT a valid checkpoint estimate by itself; must prove every omitted full-buffer chunk is constructor-exact and preserve scratch/lookahead slots',corr_bytes_per_edge_fp16=corr_elements*2,corr_bytes_per_edge_fp32=corr_elements*4,initialization_directed_edge_upper_bound=12*11,historical_archive_count=len(records),max_historical_uncompressed_output_bytes=maxout,max_historical_archive_bytes=maxarc,last_resource=last,remote_safety_floor_bytes=10*2**30,historical_headroom_above_floor_bytes=last['data_free_bytes']-10*2**30,conservative_serial_storage_formula='C0_saved + S1_saved + S0_saved + sum(4 output bounds) + max(one temporary archive bound) + measured scratch bound + 10GiB <= free_at_launch',four_raw_plus_single_archive_historical_bound_bytes=4*maxout+maxarc,historical_numeric_ranges=metrics,estimated_new_GPU_peak='UNKNOWN_NOT_MEASURED',estimated_new_GPU_time='UNKNOWN_NOT_MEASURED',C0_actual_serialized_bytes=None,S1_actual_bytes=None,S0_actual_bytes=None)
dump('evidence/RESOURCE_CALCULATION.json',resource)
summary=dict(source_files=len(list((root/'source_evidence').rglob('*.py'))),mutable_attribute_assignments=len(attrs),historical_archives=len(records),historical_24_runs=len(master),resource={k:resource[k] for k in ['full_video_logical_bytes','video_cpu_logical_bytes','video_cuda_logical_bytes','illustrative_13_slot_bytes','corr_bytes_per_edge_fp16','corr_bytes_per_edge_fp32','max_historical_uncompressed_output_bytes','max_historical_archive_bytes','historical_headroom_above_floor_bytes','four_raw_plus_single_archive_historical_bound_bytes']},historical_numeric_ranges=metrics,gpu_or_model_imports_performed=False,remote_operations=0)
print(json.dumps(summary,ensure_ascii=False,indent=2))
