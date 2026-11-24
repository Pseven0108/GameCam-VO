import pathlib,sys,json,zipfile,hashlib,collections,time,csv,io
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
A=pathlib.Path(r'D:/aaa/GameCam-VO/experiments/DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def put(p,d):
 with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False,allow_nan=False)
reference=json.loads((A/'reports/RAW_DATA_ARCHIVE_INDEX.json').read_text(encoding='utf-8'))
allout={};tests=[];starts=time.monotonic()
for arm in ['E0','E1']:
 p=next((A/'raw_archives').glob(arm+'_*.zip'));ref=next(d for d in reference if d['arm']==arm)
 actualsha=sha(p);assert actualsha==ref['sha256']
 r=dict(archive=str(p),bytes=p.stat().st_size,sha256=actualsha,outer_identity_match=True,members=[],payload_checks=[],event_counts={},event_keys={},first_event_samples={},target_records=[])
 with zipfile.ZipFile(p) as z:
  names=z.namelist();manifest=json.loads(z.read('_TASK004A_ARCHIVE_MANIFEST.json'))
  assert set(names)==set(manifest['files'])|{'_TASK004A_ARCHIVE_MANIFEST.json'}
  for name,expect in manifest['files'].items():
   h=hashlib.sha256();size=0
   with z.open(name) as f:
    for block in iter(lambda:f.read(4*1024**2),b''):h.update(block);size+=len(block)
   passed=h.hexdigest()==expect['sha256'] and size==expect['bytes'];assert passed,(arm,name)
   r['payload_checks'].append(dict(member=name,bytes=size,sha256=h.hexdigest(),sha256_match=True,crc_checked_by_full_stream_read=True))
  for i in z.infolist():r['members'].append(dict(name=i.filename,bytes=i.file_size,compressed_bytes=i.compress_size,crc32=f'{i.CRC:08x}'))
  small={}
  for i in z.infolist():
   if i.file_size<200000 and i.filename.endswith(('.json','.yaml')) and not i.filename.startswith('runtime_cache/'):
    raw=z.read(i)
    try:small[i.filename]=json.loads(raw)
    except ValueError:small[i.filename]=raw.decode(errors='replace')
  r['small_metadata']=small
  droot=ROOT/'evidence'/'historical'/arm;droot.mkdir(parents=True,exist_ok=False)
  for name in ['native_config.yaml','policy.json','model_input.json','model_result.json','PROCESS_RECEIPT.json','_TASK004A_ARCHIVE_MANIFEST.json']:(droot/name).write_bytes(z.read(name))
  counts=collections.Counter();keys={};samples={};decisions=[];graph=[];stages=[]
  with z.open('observer.jsonl') as f,(droot/'TARGET_OBSERVER_EXCERPTS.jsonl').open('xb') as excerpts:
   for line in f:
    d=json.loads(line);eventtype=d['type'];assert isinstance(d['event'],int);counts[eventtype]+=1;keys.setdefault(eventtype,set()).update(d.keys());samples.setdefault(eventtype,d)
    if d.get('ba_id') in ([550,551,552] if arm=='E0' else [660,661,662]):r['target_records'].append(d);excerpts.write(line)
    if eventtype=='keyframe_decision':decisions.append(d)
    if eventtype=='ba_before':graph.append(dict(ba_id=d['ba_id'],stage=d['stage'],trigger_rgb_id=d['trigger_rgb_id'],t0=d['t0'],t1=d['t1'],edge_slots=d['edge_slots'],rows=[dict(slot=q['slot'],rgb_id=q['rgb_id']) for q in d['rows']],native_iterations=d['native_iterations_requested'],timestamp_ns=d['time_unix_ns']))
    if eventtype=='stage_boundary':stages.append(d)
  r.update(event_counts=dict(counts),event_keys={k:sorted(v) for k,v in keys.items()},first_event_samples=samples,framewise_decisions=decisions,ba_graph_schedule=graph,stage_boundaries=stages,all_crc_pass=True,internal_sha256_matches=len(r['payload_checks']))
  assert len(decisions)==487
  assert len([d for d in r['target_records'] if d['type']=='ba_before'])==3
  tests.extend([dict(check=arm+'_archive_identity',passed=True),dict(check=arm+'_member_crc_and_sha',passed=True,payloads=len(r['payload_checks'])),dict(check=arm+'_487_decisions',passed=True),dict(check=arm+'_three_target_BA_triplets',passed=len(r['target_records'])==9)])
 allout[arm]=r
 print(json.dumps(dict(arm=arm,sha256=actualsha,members=len(r['members']),payload_sha_matches=r['internal_sha256_matches'],crc='PASS',frame_decisions=len(decisions),target_records=len(r['target_records']),event_counts=r['event_counts'])),flush=True)
put(ROOT/'evidence/PHASE0_LOCAL_ARCHIVE_VALIDATION.json',allout)
put(ROOT/'test_logs/ARCHIVE_IDENTITY_AND_PARSER_CHECKS.json',dict(utc=datetime.now(timezone.utc).isoformat(),checks=tests,all_checks_pass=all(t['passed'] for t in tests),elapsed_seconds=time.monotonic()-starts,parser_note='type is event category; event is ordinal, not category. Supersedes initial exploratory grouping.'))
print('VALIDATION_COMPLETE',len(tests),'checks',round(time.monotonic()-starts,3),'seconds')
