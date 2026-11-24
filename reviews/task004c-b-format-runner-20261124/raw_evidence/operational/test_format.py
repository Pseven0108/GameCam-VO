"""Pinned Format adapter tests, with real installed timm and CPU-only storage."""
import copy
from enum import Enum
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import torch
from timm.layers.format import Format, get_channel_dim, get_spatial_dim
from control_common import ControlError
from native_control import timm_format_adapter as a
from native_control.snapshot import ObjectEncoder, load_state, save_state

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

class Foreign(Enum):
    A = 'NHWC'

class ForeignString(str):
    pass

class FormatTests(unittest.TestCase):
    def rt(self, value):
        with tempfile.TemporaryDirectory(dir=OUT) as parent:
            p = Path(parent)/'checkpoint'
            save_state(value, p, provenance={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE'})
            return load_state(p)[0]

    def test_nchw_identity(self): self.assertIs(self.rt(Format.NCHW), Format.NCHW)
    def test_nhwc_identity(self): self.assertIs(self.rt(Format.NHWC), Format.NHWC)
    def test_ncl_identity(self): self.assertIs(self.rt(Format.NCL), Format.NCL)
    def test_nlc_identity(self): self.assertIs(self.rt(Format.NLC), Format.NLC)

    def test_shared_references(self):
        restored=self.rt({'a':Format.NHWC, 'list':[Format.NHWC,Format.NHWC]})
        self.assertIs(restored['a'], restored['list'][0])
        self.assertIs(restored['a'], restored['list'][1])
        self.assertIs(restored['a'], Format.NHWC)

    def test_configdict_interoperation(self):
        from mmcv.utils import ConfigDict
        c=ConfigDict({'format':Format.NHWC, 'nested':{'format':Format.NCHW}})
        r=self.rt(c)
        self.assertIs(r['format'], Format.NHWC)
        self.assertIs(r['nested']['format'], Format.NCHW)
        self.assertIs(type(r), ConfigDict)

    def test_dictionary_key_type(self):
        r=self.rt({Format.NHWC:[Format.NHWC]})
        self.assertIs(next(iter(r)), Format.NHWC)

    def test_spatial_channel_behavior(self):
        r=self.rt([Format.NCHW,Format.NHWC,Format.NCL,Format.NLC])
        for x,y in zip(r,[Format.NCHW,Format.NHWC,Format.NCL,Format.NLC]):
            self.assertEqual(get_spatial_dim(x),get_spatial_dim(y))
            self.assertEqual(get_channel_dim(x),get_channel_dim(y))

    def test_plain_string_not_enum(self): self.assertIs(type(self.rt('NHWC')), str)
    def test_unknown_enum_rejected(self):
        with self.assertRaises(ControlError): ObjectEncoder().encode(Foreign.A)
    def test_unknown_string_subclass_rejected(self):
        with self.assertRaises(ControlError): ObjectEncoder().encode(ForeignString('NHWC'))

    def bad(self, mutate):
        n=a.encode_member(Format.NHWC)
        mutate(n)
        with self.assertRaises(ControlError): a.restore_member(Format,n)

    def test_wrong_class(self): self.bad(lambda n:n.update({'class':'timm.layers.format:Other'}))
    def test_wrong_tag(self): self.bad(lambda n:n.update({'kind':'generic_enum'}))
    def test_unknown_name(self): self.bad(lambda n:n.update({'member_name':'UNKNOWN'}))
    def test_name_value_mismatch(self): self.bad(lambda n:n.update({'member_value':'NCHW'}))
    def test_string_name_required(self): self.bad(lambda n:n.update({'member_name':False}))
    def test_string_value_required(self): self.bad(lambda n:n.update({'member_value':False}))
    def test_package_version_pin(self): self.bad(lambda n:n['pin'].update({'timm':'0.9.11'}))
    def test_source_pin(self): self.bad(lambda n:n['pin'].update({'source_sha256':'0'*64}))
    def test_missing_field(self): self.bad(lambda n:n.pop('pin'))
    def test_extra_field(self): self.bad(lambda n:n.update({'attrs':[]}))

    def test_fresh_process(self):
        with tempfile.TemporaryDirectory(dir=OUT) as parent:
            p=Path(parent)/'checkpoint'
            save_state({'fmt':Format.NHWC,'all':list(Format)},p,provenance={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE'})
            code="from native_control.snapshot import load_state; from timm.layers.format import Format; import torch,sys; r,_=load_state(sys.argv[1]); assert r['fmt'] is Format.NHWC; assert all(x is y for x,y in zip(r['all'],list(Format))); assert not torch.cuda.is_initialized(); print('FRESH_PROCESS_IDENTITY_PASS')"
            child=subprocess.run([sys.executable,'-B','-c',code,str(p)],capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
            (OUT/'fresh_process.stdout.txt').write_text(child.stdout)
            (OUT/'fresh_process.stderr.txt').write_text(child.stderr)
            (OUT/'fresh_process.receipt.json').write_text(json.dumps({'exit_code':child.returncode}))
            self.assertEqual(child.returncode,0,child.stderr)
            self.assertIn('FRESH_PROCESS_IDENTITY_PASS',child.stdout)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(FormatTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'passed':result.wasSuccessful(),'cuda_initialized':torch.cuda.is_initialized(),'kind':'REAL_INSTALLED_ENUM_CPU_TEST'}
    (OUT/'FORMAT_UNIT_TEST_REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
    sys.exit(0 if result.wasSuccessful() and not torch.cuda.is_initialized() else 1)
