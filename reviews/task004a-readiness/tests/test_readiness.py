"""Integration/failure tests for the CPU-only release. Uses only synthetic attempts."""
import ast
import csv
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE/'tools'), str(BASE/'fixtures')]

from archive import MANIFEST, receive_copy, verify_zip
from attempt_contract import validate_attempt
from contracts import (DISK_ADMISSION, ORDER, POLICY_SHA, ROOT, need, new_json,
                       read_json, stat_sha, strict_json, verify_policy)
from f0_mock import exercise
from mock_child import synthetic_gt
from scheduler import cpu_environment, run_campaign
from trace_audit import parse


class Readiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need(os.environ.get('CUDA_VISIBLE_DEVICES', '') == '', 'CUDA must be hidden')
        cls.success = ROOT/'evaluation/mock_campaign_03'
        cls.received = ROOT/'evaluation/mock_receiver_03'
        cls.inputs = ROOT/'assets'
        cls.failure_dir = ROOT/'evaluation/safety_tests_02'
        cls.failure_dir.mkdir(exist_ok=False)
        cls.runs = sorted(p for p in cls.success.iterdir() if (p/'LAUNCH_RECEIPT.json').exists())
        cls.first = cls.runs[0]

    def drive(self, name, **args):
        root, dest = self.failure_dir/f'{name}_run', self.failure_dir/f'{name}_received'
        report = run_campaign(root, dest, self.inputs, ROOT/'fixtures/mock_child.py', synthetic_gt(), **args)
        return report, root, dest

    def rows(self, name):
        with (self.success/name).open(encoding='utf-8-sig', newline='') as f:
            return {r['arm']:r for r in csv.DictReader(f)}

    def test_01_eight_serial_attempts_and_verified_receipts(self):
        r = read_json(self.success/'CAMPAIGN_RESULT.json')
        self.assertEqual(r['status'], 'MOCK_COMPLETE')
        self.assertEqual(tuple(r['started']), ORDER)
        self.assertEqual(tuple(r['completed']), ORDER)
        self.assertEqual(r['gpu_runs'], 0)
        self.assertEqual(len(self.runs), 8)
        receipts = [read_json(p/'LAUNCH_RECEIPT.json') for p in self.runs]
        self.assertEqual(len({x['attempt_id'] for x in receipts}), 8)
        self.assertEqual([x['previous'] for x in receipts], [None]+list(ORDER[:-1]))
        for arm, p, launch in zip(ORDER,self.runs,receipts):
            self.assertEqual((launch['arm'],launch['policy_sha256'],launch['model_started']), (arm,POLICY_SHA[arm],False))
            end = read_json(p/'PROCESS_RECEIPT.json')
            self.assertEqual((end['pid'],end['exit_code']), (launch['pid'],0))
            self.assertGreaterEqual(end['finished_utc'],launch['started_utc'])
            record = read_json(self.received/f'{p.name}.verified.json')
            self.assertEqual(record['status'],'VERIFIED_COPY')
            self.assertFalse(record['cleanup_authorized'])
            self.assertEqual(stat_sha(self.received/f'{p.name}.zip'),record['source']['sha256'])
            self.assertEqual(stat_sha(self.success/'archives'/f'{p.name}.zip'),record['received']['sha256'])

    def test_02_missing_keyframe_has_export_but_no_direct_score(self):
        r = self.rows('SYNTHETIC_ENDPOINT_RETENTION.csv')
        fixed = self.rows('SYNTHETIC_FIXED_RGB_ENDPOINT_METRICS.csv')
        direct = self.rows('SYNTHETIC_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv')
        self.assertEqual([r['E3'][k] for k in ('rgb312_retained_kf','rgb328_retained_kf','joint_local_ba_return',
                         'both_in_pose_window_count','rgb328_export_origin','rgb328_filler_temp_valid')],
                         ['True','False','True','0','FILLER_RESULT','True'])
        self.assertEqual(fixed['E3']['status'],'VALID')
        self.assertEqual(direct['E3']['status'],'ENDPOINT_UNAVAILABLE')
        self.assertEqual(direct['E3']['displacement_ratio_pct'],'')
        self.assertEqual(r['E7']['endpoint_kf_retention_rate'],'0.0')
        self.assertEqual(r['E0']['rgb328_export_origin'],'REINSERTED_KEYFRAME')
        e0 = self.runs[ORDER.index('E0')]
        j = read_json(e0/'VALIDATION_RECEIPT.json')
        self.assertEqual([x['status'] for x in j['endpoint_metrics']], ['VALID','VALID'])
        self.assertNotEqual(j['endpoint_metrics'][0]['estimate_raw_length'],j['filler_diagnostics'][0]['estimate_raw_length'])

    def test_03_nonzero_process_exit_stops_and_preserves_partial(self):
        r, run, dest = self.drive('child_failed',fail_arm='E4')
        self.assertEqual((r['failed_arm'],r['started'],r['completed']),('E4',['E3','E4'],['E3']))
        self.assertIn('exited 31',r['failure'])
        failed = next(p for p in run.iterdir() if p.name.startswith('02-E4-'))
        self.assertEqual(read_json(failed/'PROCESS_RECEIPT.json')['exit_code'],31)
        self.assertIn('synthetic native pre-return failure',(failed/'process.stderr.txt').read_text())
        partial = parse(failed/'observer.jsonl',arm='E4')
        self.assertEqual(partial.unfinished[0]['status'],'NATIVE_RETURN_NOT_OBSERVED')
        self.assertTrue((dest/f'{failed.name}.verified.json').is_file())

    def test_04_zero_exit_with_unpaired_trace_stops(self):
        r, run, _ = self.drive('trace_failed',corrupt_arm='E3')
        self.assertEqual((r['failed_arm'],r['started'],r['completed']),('E3',['E3'],[]))
        self.assertIn('missing BA return/clamp',r['failure'])
        failed = next(p for p in run.iterdir() if p.name.startswith('01-E3-'))
        self.assertEqual(read_json(failed/'PROCESS_RECEIPT.json')['exit_code'],0)

    def test_05_space_deficit_refuses_launch(self):
        r, root, dest = self.drive('disk_failed',free=lambda _:DISK_ADMISSION-1)
        self.assertEqual((r['started'],r['completed'],r['failed_arm']),([],[],'E3'))
        self.assertIn('insufficient disk',r['failure'])
        self.assertEqual(list(root.glob('*/LAUNCH_RECEIPT.json')),[])
        self.assertEqual(list(dest.iterdir()),[])

    def test_06_space_rechecked_before_next_without_auto_cleanup(self):
        def free(_):
            return (DISK_ADMISSION-1 if any((self.failure_dir/'next_space_received').glob('*.verified.json'))
                    else DISK_ADMISSION)
        r, root, dest = self.drive('next_space',free=free)
        self.assertEqual((r['started'],r['completed'],r['failed_arm']),(['E3'],['E3'],'E4'))
        self.assertEqual(len(list(dest.glob('*.verified.json'))),1)
        self.assertEqual(len(list(root.glob('01-E3-*/observer.jsonl'))),1)

    def test_07_archive_copy_failure_stops_group_without_deleting_output(self):
        with patch('scheduler.receive_copy',side_effect=ValueError('receiving ZIP SHA-256 mismatch (injected)')):
            r, root, dest = self.drive('copy_failed')
        self.assertEqual((r['started'],r['completed'],r['failed_arm']),(['E3'],[],'E3'))
        self.assertIn('receiving ZIP SHA-256 mismatch',r['failure'])
        self.assertEqual(list(dest.glob('*.verified.json')),[])
        self.assertEqual(len(list(root.glob('01-E3-*/observer.jsonl'))),1)

    def test_08_policy_byte_change_refused(self):
        path = self.failure_dir/'tampered_policy.json'
        path.write_bytes((self.inputs/'policies/E3.json').read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            verify_policy(path,'E3')
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            verify_policy(self.inputs/'policies/E4.json','E3')

    def test_09_existing_campaign_refuses_retry(self):
        with self.assertRaisesRegex(ValueError,'no resume or retry'):
            run_campaign(self.success,self.received,self.inputs,ROOT/'fixtures/mock_child.py',synthetic_gt())

    def test_10_trace_rejects_mutated_pair_counter_and_filler_key(self):
        raw = (self.first/'observer.jsonl').read_bytes().splitlines(keepends=True)
        for kind, key, value, expect in (
            ('ba_after_native','ba_id',99,'mismatched BA'),
            ('ba_after_native','pid',1,'trace schema or PID'),
            ('ba_after_clamp','stage','final_ba_phase_1','mismatched BA'),
            ('ba_after_clamp','full_disparity_grid',dict(scope='ALL_PIXELS_ACTIVE_SLOT_PREFIX',active_slots=1,total=1,
                               negative=0,nonfinite=0,float32_floor_count=0),'invalid full disparity counters'),
            ('filler_pose_update','filler_batch',99,'filler update frame list mismatch'),
        ):
            with self.subTest(event=kind,field=key):
                modified = list(raw)
                pos = next(i for i,x in enumerate(raw) if strict_json(x)['type']==kind)
                row = strict_json(raw[pos]); row[key]=value
                modified[pos] = (json.dumps(row,separators=(',',':'))+'\n').encode()
                path = self.failure_dir/f'bad_{kind}_{key}.jsonl'
                path.write_bytes(b''.join(modified))
                pid = read_json(self.first/'tracking_child_ok.json')['pid']
                with self.assertRaisesRegex(ValueError,expect):
                    parse(path,arm='E3',complete=True,expected_pid=pid)

    def test_11_corrupt_zip_and_crc_valid_wrong_contents(self):
        src = self.failure_dir/'seal_payload'; src.mkdir()
        (src/'frame_ids.txt').write_bytes(b'312 328')
        original = self.failure_dir/'stored_original.zip'
        from zipfile import ZIP_STORED
        with ZipFile(original,'x',ZIP_STORED) as z:
            z.write(src/'frame_ids.txt','frame_ids.txt')
            z.writestr(MANIFEST,json.dumps(dict(schema='GAMECAM_TASK004A_ATTEMPT_ARCHIVE_V1',attempt_id='TEST',
                       files={'frame_ids.txt':dict(bytes=7,sha256=stat_sha(src/'frame_ids.txt'))})))
        receipt=verify_zip(original,expected_attempt='TEST')
        bad = self.failure_dir/'corrupt_crc.zip'
        bad.write_bytes(original.read_bytes().replace(b'312 328',b'312 329',1))
        with self.assertRaisesRegex(Exception,'Bad CRC'):
            verify_zip(bad)
        with self.assertRaisesRegex(ValueError,'receiving ZIP SHA-256 mismatch'):
            receive_copy(bad,self.failure_dir/'copy_broken.zip',receipt)
        hash_bad=self.failure_dir/'new_crc_wrong_payload.zip'
        with ZipFile(original) as z, ZipFile(hash_bad,'x',ZIP_STORED) as other:
            other.writestr('frame_ids.txt','312 329')
            other.writestr(MANIFEST,z.read(MANIFEST))
        with ZipFile(hash_bad) as z:
            self.assertIsNone(z.testzip())
        with self.assertRaisesRegex(ValueError,'ZIP payload SHA mismatch'):
            verify_zip(hash_bad)

    def test_12_admission_success_claim_does_not_bypass_native_guard(self):
        r = subprocess.run([sys.executable,'-B',str(ROOT/'tools/scheduler.py'),'--native'],
                           capture_output=True,text=True,timeout=12,env=cpu_environment())
        self.assertNotEqual(r.returncode,0)
        self.assertIn('no GPU dispatch authorized',r.stderr)
        new_json(self.failure_dir/'NATIVE_GUARD_COMMAND.json',dict(argv=r.args,exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
        t = ast.parse((self.inputs/'candidates/task004_run_segment.py').read_bytes())
        self.assertEqual(t.body[2].value.func.id,'require_approved_runtime')
        policy = ast.parse((self.inputs/'candidates/task004_controls.py').read_bytes())
        f = next(n for n in policy.body if isinstance(n,ast.FunctionDef) and n.name=='require_approved_runtime')
        self.assertEqual([type(x) for x in f.body], [ast.Raise])
        self.assertEqual(f.body[0].exc.func.id,'SystemExit')

    def test_13_f0_and_f2_control_flow_mock(self):
        f0,f2 = exercise(0),exercise(2)
        self.assertNotEqual(f0['events'],f2['events'])
        self.assertEqual(f0['keyframe_index'],f2['keyframe_index'])
        new_json(self.failure_dir/'F0_CONTROL_FLOW_CPU_MOCK.json',dict(F0=f0,F2=f2,status='PASS_CPU_CALL_PATH_ONLY'))

    def test_14_launch_receipt_and_staged_policy_must_agree(self):
        p = self.failure_dir/'changed_receipt'/self.first.name
        shutil.copytree(self.first,p)
        (p/'policy.json').write_bytes((self.inputs/'policies/E4.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'launch/terminal receipt mismatch'):
            validate_attempt(p,'E3',POLICY_SHA['E3'],self.inputs/'candidates/r2_sealed_config.yaml')


if __name__ == '__main__':
    unittest.main(verbosity=2)
