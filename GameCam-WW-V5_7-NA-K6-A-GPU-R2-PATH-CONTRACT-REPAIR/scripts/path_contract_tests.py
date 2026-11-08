"""CPU-only positive and adversarial tests for RuntimePins v2."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import traceback

import runtime_dependency_pins as runtime
from runtime_dependency_pins import PinError, RuntimePins

def digest(data):
    return hashlib.sha256(data).hexdigest()

def expect_reject(fn, text):
    try:
        fn()
    except PinError as exc:
        if text not in str(exc):
            raise AssertionError('wrong rejection: ' + str(exc)) from exc
        return {'rejected': True, 'reason': str(exc), 'traceback': traceback.format_exc()}
    raise AssertionError('expected RuntimePins rejection: ' + text)

def fixture_record(alias, target, root, data, expected=None, size=None):
    return {'path_linux': str(alias), 'real_linux': str(target.resolve()),
            'allowed_root_linux': str(root), 'allowed_root_real_linux': str(root.resolve()),
            'bytes': len(data) if size is None else size,
            'sha256': digest(data) if expected is None else expected}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    pins=RuntimePins(a.root); results=[]
    def run(name, fn):
        try:
            detail=fn(); results.append({'name':name,'passed':True,'detail':detail})
        except BaseException as exc:
            results.append({'name':name,'passed':False,'error':str(exc),'traceback':traceback.format_exc()})

    run('original_mnt_alias_resolves', lambda: pins.checked_file(pins.spec['config']))
    def canonical_check():
        resolved=str(Path(pins.spec['config']['path_linux']).resolve(strict=True))
        if resolved!=pins.spec['config']['real_linux']:
            raise AssertionError('canonical mismatch: '+resolved)
        return {'resolved':resolved,'expected':pins.spec['config']['real_linux'],'equal':True}
    run('canonical_path_matches_real_linux',canonical_check)
    run('original_config_sha_unchanged', lambda: {'sha256':pins.checked_file(pins.spec['config'])['sha256'],
         'expected':pins.spec['config']['sha256']})

    with tempfile.TemporaryDirectory(prefix='k6a-pathfix-') as temp:
        root=Path(temp)/'allowed'; files=root/'files'; files.mkdir(parents=True)
        target=files/'target.bin'; content=b'fixed bytes 123'; target.write_bytes(content)
        alias=root/'alias.bin'; alias.symlink_to(target)
        record=fixture_record(alias,target,root,content)
        run('same_inode_alias_is_accepted', lambda: {'check':pins.checked_file(record),
             'same_dev_inode':(alias.stat().st_dev,alias.stat().st_ino)==(target.stat().st_dev,target.stat().st_ino)})

        other=files/'other.bin'; other.write_bytes(content)
        wrong=root/'wrong.bin'; wrong.symlink_to(other)
        run('wrong_path_alias_is_rejected', lambda: expect_reject(lambda:pins.checked_file(record,request=wrong),'LOAD_PATH_NOT_ALLOWLISTED'))

        link=root/'retargeted.bin'; link.symlink_to(other)
        changed_target_record=fixture_record(link,target,root,content)
        run('changed_symlink_target_is_rejected', lambda: expect_reject(lambda:pins.checked_file(changed_target_record),'SYMLINK_TARGET_CHANGED'))

        changed=root/'changed.bin'; changed.write_bytes(b'changed bytes!!')
        changed_record=fixture_record(changed,changed,root,content)
        run('file_sha_change_is_rejected', lambda: expect_reject(lambda:pins.checked_file(changed_record),'FILE_SHA_MISMATCH'))

        short=root/'short.bin'; short.write_bytes(b'x')
        size_record=fixture_record(short,short,root,b'xxxx',size=4)
        run('file_size_change_is_rejected', lambda: expect_reject(lambda:pins.checked_file(size_record),'FILE_SIZE_MISMATCH'))

        replace=root/'replace.bin'; replace.write_bytes(content)
        replacement=root/'replacement.tmp'; replacement.write_bytes(content)
        replace_record=fixture_record(replace,replace,root,content)
        original_hash=runtime.hash_open_file
        def replacing_hash(stream,capture=False):
            value=original_hash(stream,capture)
            os.replace(replacement,replace)
            return value
        runtime.hash_open_file=replacing_hash
        try:
            run('replacement_during_check_is_rejected', lambda: expect_reject(lambda:pins.checked_file(replace_record),'FILE_CHANGED_DURING_CHECK'))
        finally:
            runtime.hash_open_file=original_hash

        outside=Path(temp)/'outside'; outside.mkdir(); external=outside/'external.bin'; external.write_bytes(content)
        escape=root/'escape.bin'; escape.symlink_to(external)
        escape_record=fixture_record(escape,external,root,content)
        run('path_outside_allowed_root_is_rejected', lambda: expect_reject(lambda:pins.checked_file(escape_record),'REAL_PATH_OUTSIDE_ALLOWED_ROOT'))

    def weight_check():
        checked=[pins.checked_file(row) for row in pins.weights.values()]
        if len(checked)!=4 or any(x['sha256']!=pins.weights[next(k for k,v in pins.weights.items() if v['path_linux']==x['path'])]['sha256'] for x in checked):
            raise AssertionError('weight allowlist mismatch')
        return {'count':len(checked),'files':checked}
    run('all_four_weight_paths_complete',weight_check)
    run('k4_contract_path_complete',lambda:pins.checked_file(pins.spec['k4_live_contract']))

    passed=all(x['passed'] for x in results)
    report={'suite':'K6-A-GPU-R2-PATHFIX CPU filesystem tests','passed':passed,'tests':results,
            'test_count':len(results),'torch_imported':'torch' in __import__('sys').modules,
            'checkpoint_deserialized':False,'model_constructed':False,'cuda_executed':False,
            'real_images_decoded':False,'prior_attempt_count':1,'new_attempts_created':0}
    Path(a.output).write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({'passed':passed,'test_count':len(results),'torch_imported':report['torch_imported']}))
    if not passed: raise SystemExit(2)

if __name__=='__main__': main()
