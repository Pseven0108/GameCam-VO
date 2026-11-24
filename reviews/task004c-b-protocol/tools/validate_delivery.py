"""Read-only delivery consistency checks. No model, torch, CUDA, SSH, or restore execution."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import hashlib, json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = []
def load(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def check(name, fn):
    try:
        detail = fn()
        RESULTS.append({'name': name, 'status': 'PASS', 'detail': detail})
        print('PASS ' + name)
    except Exception as exc:
        RESULTS.append({'name': name, 'status': 'FAIL', 'error': str(exc)})
        print('FAIL ' + name + ': ' + str(exc), file=sys.stderr)
def need(value, message):
    if not value:
        raise AssertionError(message)

REQUIRED = [
'TASK004C_B_PROTOCOL_SOURCE_AUDIT.md', 'TASK004C_B_COMMON_CHECKPOINT_SCHEMA.md',
'TASK004C_B_COMMON_CHECKPOINT_MANIFEST.json', 'TASK004C_B_SCHEDULE_RECORDING_PROTOCOL.md',
'TASK004C_B_S1_SCHEDULE_SCHEMA.json', 'TASK004C_B_S0_SCHEDULE_SCHEMA.json',
'TASK004C_B_CROSSOVER_MATRIX.md', 'TASK004C_B_REPLAY_VALIDATION.md',
'TASK004C_B_RESOURCE_ESTIMATE.md', 'TASK004C_B_PROTOCOL_FINAL_REVIEW.md']
def required_files():
    for name in REQUIRED:
        need((ROOT / name).is_file() and (ROOT / name).stat().st_size > 0, name)
    return {'nonempty_requested_files': len(REQUIRED)}
check('requested_deliverables_present', required_files)

def parse_json():
    files = [p for p in ROOT.rglob('*.json') if 'artifacts' not in p.relative_to(ROOT).parts]
    for path in files:
        json.loads(path.read_text(encoding='utf-8'))
    return {'parsed_files': len(files)}
check('all_delivery_json_parse', parse_json)

# Selected syntax/reference checks only; this is not a Draft2020-12 metaschema validator.
def schema_structure(schema):
    refs, nodes = [], []
    def visit(node, loc):
        if isinstance(node, bool):
            return
        need(isinstance(node, dict), 'schema node ' + loc)
        nodes.append(loc)
        if 'type' in node:
            types = node['type'] if isinstance(node['type'], list) else [node['type']]
            need(bool(types) and set(types) <= {'object','array','string','integer','number','boolean','null'}, 'type ' + loc)
        if 'required' in node:
            need(isinstance(node['required'], list) and len(set(node['required'])) == len(node['required']), 'required ' + loc)
            need(all(isinstance(k, str) for k in node['required']), 'required names ' + loc)
            if 'properties' in node:
                need(set(node['required']) <= set(node['properties']), 'required undefined properties ' + loc)
        if 'pattern' in node:
            re.compile(node['pattern'])
        if '$ref' in node:
            ref = node['$ref']
            need(ref.startswith('#/'), 'external reference not allowed: ' + ref)
            target = schema
            for part in ref[2:].split('/'):
                target = target[part.replace('~1','/').replace('~0','~')]
            need(isinstance(target, (dict, bool)), 'ref target ' + ref)
            refs.append(ref)
        for key in ('$defs','properties','patternProperties','dependentSchemas'):
            for label, child in node.get(key, {}).items():
                visit(child, loc + '/' + key + '/' + label)
        for key in ('items','contains','additionalProperties','unevaluatedProperties','propertyNames','if','then','else','not'):
            if key in node:
                visit(node[key], loc + '/' + key)
        for key in ('allOf','oneOf','anyOf','prefixItems'):
            if key in node:
                need(isinstance(node[key], list), 'schema array ' + loc)
                for i, child in enumerate(node[key]):
                    visit(child, loc + '/' + key + '/' + str(i))
    need(schema.get('$schema') == 'https://json-schema.org/draft/2020-12/schema', 'schema dialect')
    visit(schema, '#')
    return {'schema_nodes_checked': len(nodes), 'resolved_internal_references': len(refs),
            'scope': 'selected syntax / required-property / local-reference checks, not full metaschema certification'}
for sid in ('S1','S0'):
    check(sid + '_schema_structure_and_refs', lambda sid=sid: schema_structure(load('TASK004C_B_' + sid + '_SCHEDULE_SCHEMA.json')))

def schedule_coverage():
    details=[]
    for sid in ('S1','S0'):
        schema=load('TASK004C_B_' + sid + '_SCHEDULE_SCHEMA.json')
        event=schema['$defs']['event']
        kinds=event['properties']['kind']['enum']
        rules=event['allOf']
        found=[rule['if']['properties']['kind']['const'] for rule in rules]
        need(len(kinds)==22 and len(found)==22 and set(kinds)==set(found), 'event rule coverage ' + sid)
        payload_keys=set(event['properties']['payload']['properties'])
        for rule in rules:
            required=rule['then']['properties']['payload']['required']
            need(bool(required) and set(required) <= payload_keys, 'undefined event payload ' + sid)
        need(schema['properties']['complete']['const'] is True, 'complete schedule required')
        details.append({'schedule':sid,'event_kinds':len(kinds),'event_payload_rules':len(rules)})
    return details
check('all_22_event_kinds_have_payload_requirements', schedule_coverage)

def schema_pair():
    s1=load('TASK004C_B_S1_SCHEDULE_SCHEMA.json')
    s0=load('TASK004C_B_S0_SCHEDULE_SCHEMA.json')
    need(s1['properties']['schedule_id']['const']=='S1' and s0['properties']['schedule_id']['const']=='S0','schedule id')
    need(s1['properties']['producer_arm']['const']=='B1' and s0['properties']['producer_arm']['const']=='B4','producer arm')
    need(s1['properties']['producer_D']['const']==1 and s0['properties']['producer_D']['const']==0,'producer D')
    for s in (s1,s0):
        s['title']='NORMALIZED_TITLE'
        for key in ('schedule_id','producer_arm','producer_D'):
            s['properties'][key]['const']='NORMALIZED_' + key
    need(s1==s0, 'unintended S1 / S0 contract difference')
    return 'Only title, schedule_id, producer_arm, producer_D differ'
check('S1_S0_same_contract_except_producer', schema_pair)

manifest=load('TASK004C_B_COMMON_CHECKPOINT_MANIFEST.json')
def not_checkpoint():
    need(manifest['artifact_kind']=='DESIGN_TEMPLATE_NOT_A_CHECKPOINT','artifact kind')
    need(manifest['status']=='NOT_CAPTURED' and manifest['complete'] is False, 'template state')
    for field in ('capture_authorized','restore_implemented','restore_runtime_verified','snapshot_exists'):
        need(manifest[field] is False, field)
    need(manifest['C0_content_sha256'] is None, 'actual C0 hash must not exist')
    need(manifest['boundary']['init_D']==0, 'common init D')
    return 'No C0 / capture / restore success claim in design manifest'
check('C0_is_explicitly_uncaptured_design', not_checkpoint)

def tensors():
    names=[t['name'] for t in manifest['tensors']]
    need(len(names)==47 and len(set(names))==47,'47 distinct tensor families')
    required={'name','dtype','shape','stride','layout','device','contiguous','storage_offset','storage_id',
              'logical_value_sha256','storage_byte_sha256','file_sha256','requires_grad','is_shared','endianness','byte_size'}
    for tensor in manifest['tensors']:
        need(tensor['capture_status']=='NOT_CAPTURED' and tensor['required'] is True, tensor['name'])
        meta=tensor['live_metadata']
        need(required <= set(meta), 'incomplete metadata schema ' + tensor['name'])
        need(meta['name']==tensor['name'] and all(v is None for k,v in meta.items() if k!='name'), 'fabricated live tensor metadata')
    return {'tensor_families':47,'live_tensor_hashes':0}
check('tensor_design_metadata_complete_but_not_fabricated', tensors)

def source_identities():
    source=load('evidence/EXTRA_SOURCE_IDENTITY.json')
    need(source['commit']=='c3414af6047d06bafc1a6645d09f23247f3b2cdc'==manifest['baseline_commit'],'baseline commit')
    need(len(source['files'])==8,'eight supplemental sources')
    tree=load(source['official_tree_evidence']['package_path'])
    need(tree['sha']==source['commit'] and tree.get('truncated') is False, 'official frozen tree identity')
    need(digest(ROOT/source['official_tree_evidence']['package_path'])==source['official_tree_evidence']['sha256'], 'tree file SHA')
    tree_blobs={entry['path']:entry['sha'] for entry in tree['tree'] if entry['type']=='blob'}
    dual=0
    for item in source['files']:
        data=(ROOT/'source_evidence'/'frozen'/item['path']).read_bytes()
        # Actual Git header terminator is one NUL byte.
        blob=hashlib.sha1(b'blob '+str(len(data)).encode()+bytes([0])+data).hexdigest()
        need(blob==item['git_blob']==item['expected_blob']==tree_blobs[item['path']],'Git Blob ' + item['path'])
        need(hashlib.sha256(data).hexdigest()==item['sha256'],'SHA ' + item['path'])
        if item.get('expected_frozen_sha256'):
            need(item['expected_frozen_sha256']==item['sha256'],'prior frozen SHA ' + item['path'])
            dual+=1
    return {'Git_Blob_matches':8,'additional_prior_frozen_SHA_matches':dual}
check('supplemental_source_Git_Blob_and_SHA', source_identities)

def protected_inputs():
    before=load('evidence/PROTECTED_INPUTS_BEFORE.json')
    output=[]
    for item in before:
        path=Path(item['path']); stat=path.stat()
        actual=digest(path)
        rec={'path':item['path'],'sha256':actual,'bytes':stat.st_size,'mtime_ms':stat.st_mtime_ns/1e6,
             'sha256_match':actual==item['sha256'],'size_match':stat.st_size==item['bytes'],
             'mtime_precision_tolerance_ms':0.01,'mtime_match':abs(stat.st_mtime_ns/1e6-item['mtime_ms'])<=0.01}
        output.append(rec)
    report={'utc':datetime.now(timezone.utc).isoformat(),'files_checked':len(output),
            'all_unchanged':all(r['sha256_match'] and r['size_match'] and r['mtime_match'] for r in output),'files':output}
    (ROOT/'evidence/PROTECTED_INPUTS_AFTER.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    need(report['all_unchanged'],'protected original file changed')
    return {'original_files_unchanged':len(output),'scope':'source/config/history inputs; no fresh remote attestation'}
check('protected_original_files_unchanged', protected_inputs)

resource=load('evidence/RESOURCE_CALCULATION.json')
def resource_math():
    rows=resource['video_buffers']
    need(len(rows)==23,'DepthVideo ledger count')
    for r in rows:
        need(math.prod(r['shape'])*r['itemsize']==r['bytes'], r['name'])
    total=sum(r['bytes'] for r in rows)
    cpu=sum(r['bytes'] for r in rows if r['device']=='CPU')
    need(total==7468230540==resource['full_video_logical_bytes'],'video bytes')
    need(cpu==2246400000==resource['video_cpu_logical_bytes'],'CPU bytes')
    need(total-cpu==resource['video_cuda_logical_bytes'],'CUDA logical bytes')
    corr=3600*(3600+880+220+50)
    need(corr*2==resource['corr_bytes_per_edge_fp16'] and corr*4==resource['corr_bytes_per_edge_fp32'],'corr bytes')
    need(resource['last_resource']['data_free_bytes']-10*2**30==resource['historical_headroom_above_floor_bytes'],'headroom')
    raw=resource['max_historical_uncompressed_output_bytes']; archive=resource['max_historical_archive_bytes']
    need(4*raw+archive==6907268582==resource['four_raw_plus_single_archive_historical_bound_bytes'],'4 raw +1 archive')
    need(4*(raw+archive)==9560857988==resource['four_raw_plus_four_archives_historical_bound_bytes'],'4 raw +4 archives')
    need(resource['historical_headroom_above_floor_bytes']<4*raw,'storage conclusion')
    need(resource['C0_actual_serialized_bytes'] is None and resource['S1_actual_bytes'] is None and resource['S0_actual_bytes'] is None,'unmeasured sizes')
    return {'video_logical_bytes':total,'historical_headroom_bytes':resource['historical_headroom_above_floor_bytes'],
            'four_raw_plus_four_archives_reference_bytes':4*(raw+archive),'actual_C0_and_schedule_sizes':'UNKNOWN'}
check('resource_arithmetic_and_unknown_fields', resource_math)

def historical_reference():
    archives=load('evidence/HISTORICAL_ARCHIVE_SIZES.json')
    costs=load('evidence/HISTORICAL_COST_RECORDS.json')
    need(len(archives)==len(costs)==24,'historical record counts')
    need(max(a['uncompressed_bytes'] for a in archives)==resource['max_historical_uncompressed_output_bytes'],'raw max')
    need(max(a['archive_bytes'] for a in archives)==resource['max_historical_archive_bytes'],'archive max')
    need(all(c['status']=='COMPLETE' for c in costs),'historical cost status')
    for field, vals in resource['historical_numeric_ranges'].items():
        actual=[float(c[field]) for c in costs if c[field]!='']
        need(len(actual)==vals['count'],'cost count ' + field)
        need(math.isclose(min(actual),vals['min']) and math.isclose(max(actual),vals['max']) and math.isclose(sum(actual)/len(actual),vals['mean']),'cost range ' + field)
    return {'archive_indexes':24,'historical_complete_cost_rows':24,'new_model_runs':0}
check('historical_resource_references_match_records', historical_reference)

def boundary_and_stage_docs():
    source=(ROOT/'TASK004C_B_PROTOCOL_SOURCE_AUDIT.md').read_text(encoding='utf-8')
    matrix=(ROOT/'TASK004C_B_CROSSOVER_MATRIX.md').read_text(encoding='utf-8')
    replay=(ROOT/'TASK004C_B_REPLAY_VALIDATION.md').read_text(encoding='utf-8')
    need('第二' in source and '24' in source and '144' in source,'two-stage init and frame-tail evidence')
    for row in ('| 1 | B1 | 1 | S1 |','| 2 | B4 | 0 | S0 |','| 3 | B2 | 0 | S1 |','| 4 | B3 | 1 | S0 |'):
        need(row in matrix,'crossover row ' + row)
    need('不是' in matrix and '自然因果中介' in matrix,'causal limitation')
    need('同D' in replay and '未实测' in replay,'unexecuted numerical validation')
    return 'Two-stage boundary, four-arm matrix and nonexecuted validation explicitly distinguished'
check('critical_protocol_decisions_consistent', boundary_and_stage_docs)

def safety():
    audit=load('SECURITY_AUDIT.json')
    for field in ('gpu_requested','gpu_restarted','gpu_released','instance_shutdown','cuda_context_initialized',
                  'cuda_tensor_created','model_imported','checkpoint_deserialized','model_constructed','model_forward_executed',
                  'native_ba_executed','new_C0_captured','baseline_sources_modified','original_R2_yaml_modified','weights_modified',
                  'historical_results_modified','historical_files_deleted'):
        need(audit[field] is False,field)
    for field in ('remote_connections','gpu_device_queries','new_natural_schedules_recorded','new_formal_B_arms','new_full_487_runs'):
        need(audit[field]==0,field)
    return 'Scope flags consistent with local static task; not a fresh remote/GPU measurement'
check('safety_scope_and_no_execution_claims', safety)

failed=sum(r['status']=='FAIL' for r in RESULTS)
report={'task':'TASK004C-B-PROTOCOL','utc':datetime.now(timezone.utc).isoformat(),
        'verification_kind':'LOCAL_DELIVERY_STATIC_CONSISTENCY_NOT_RESEARCH_OR_NATIVE_RUNTIME_TEST',
        'jsonschema_package_available':False,'full_JSON_Schema_metaschema_validation':'NOT_PERFORMED_NO_DEPENDENCY_INSTALLED',
        'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
        'checks':RESULTS,'passed':len(RESULTS)-failed,'failed':failed,'exit_code':1 if failed else 0,
        'runtime_replay_tested':False,'GPU_runs':0}
(ROOT/'evidence/DELIVERY_STATIC_VALIDATION.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'passed':len(RESULTS)-failed,'failed':failed,'exit_code':report['exit_code']}))
sys.exit(report['exit_code'])
