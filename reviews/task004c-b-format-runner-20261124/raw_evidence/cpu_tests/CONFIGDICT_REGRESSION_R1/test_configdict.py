"""Executable tests using the installed MMCV/Addict classes, without CUDA."""
import io
import json
import os
from pathlib import Path
import sys
import unittest

import torch
from addict import Dict
from mmcv.utils.config import ConfigDict
from control_common import ControlError
from native_control import configdict_adapter as adapter
from native_control.snapshot import ObjectEncoder, load_state, save_state


OUT = Path(sys.argv[1])


class ConfigDictTests(unittest.TestCase):
    def roundtrip(self, value):
        path = OUT / self._testMethodName
        original = save_state(value, path, provenance={
            'artifact_kind': 'CPU_NATIVE_INTERFACE_FIXTURE',
            'test': self._testMethodName,
        })
        result, restored = load_state(path)
        graph = ObjectEncoder()
        root = graph.encode(result)
        self.assertEqual(original, restored)
        self.assertEqual(graph.nodes, restored['nodes'])
        self.assertEqual(root, restored['root'])
        return result

    def test_empty(self):
        value = self.roundtrip(ConfigDict())
        self.assertIs(type(value), ConfigDict)
        self.assertEqual(dict(value), {})
        self.assertEqual(vars(value), {'__parent': None, '__key': None, '__frozen': False})

    def test_items_and_attribute_access(self):
        cfg = ConfigDict(alpha=3, missing=None)
        object.__setattr__(cfg, 'fixture_cache', ['retained'])
        value = self.roundtrip(cfg)
        self.assertEqual((value.alpha, value['missing'], value.fixture_cache), (3, None, ['retained']))
        self.assertNotIn('fixture_cache', value)

    def test_nested_types_and_order(self):
        cfg = ConfigDict(z={'r': 7}, a=[{'q': 8}], x=4)
        nested = self.roundtrip(cfg)
        self.assertEqual(list(nested), ['z', 'a', 'x'])
        self.assertIs(type(nested.z), ConfigDict)
        self.assertIs(type(nested.a[0]), ConfigDict)
        self.assertEqual((nested.z.r, nested.a[0].q), (7, 8))

    def test_key_types(self):
        keys = ('3', 3, 3.5, ('four', 1), b'five', False, None)
        cfg = ConfigDict()
        for number, key in enumerate(keys):
            cfg[key] = number
        recovered = self.roundtrip(cfg)
        self.assertEqual(list(recovered), list(keys))
        self.assertEqual([type(key) for key in recovered], [type(key) for key in keys])
        self.assertEqual(list(recovered.values()), list(range(len(keys))))

    def test_aliases(self):
        key = ConfigDict(k=2)
        cfg = ConfigDict()
        cfg.left = cfg.right = key
        object.__setattr__(cfg, 'also', key)
        restored = self.roundtrip([cfg, vars(cfg), key])
        self.assertIs(restored[0].left, restored[0].right)
        self.assertIs(restored[0].also, restored[2])
        self.assertIs(vars(restored[0]), restored[1])

    def test_cycles(self):
        cfg = ConfigDict()
        outer = (cfg,)
        cfg.self = cfg
        cfg.outer = outer
        child = ConfigDict()
        child.parent = cfg
        cfg.child = child
        value = self.roundtrip(outer)
        self.assertIs(value[0].self, value[0])
        self.assertIs(value[0].outer, value)
        self.assertIs(value[0].child.parent, value[0])

    def test_pending_parent_key_and_detachment(self):
        parent = ConfigDict()
        child = ConfigDict(__parent=parent, __key='nested')
        dict.__setitem__(child, 'earlier', 7)
        new_parent, new_child = self.roundtrip([parent, child])
        self.assertEqual(list(new_parent), [])
        self.assertEqual(new_child.earlier, 7)
        self.assertIs(vars(new_child)['__parent'], new_parent)
        self.assertEqual(vars(new_child)['__key'], 'nested')
        new_child.later = 9
        self.assertIs(new_parent.nested, new_child)
        self.assertNotIn('__parent', vars(new_child))
        self.assertNotIn('__key', vars(new_child))

    def test_already_detached_parent_fields_stay_absent(self):
        parent = ConfigDict()
        child = ConfigDict(__parent=parent, __key='nested')
        child.earlier = 7
        new_parent, new_child = self.roundtrip([parent, child])
        self.assertIs(new_parent.nested, new_child)
        self.assertNotIn('__parent', vars(new_child))
        self.assertNotIn('__key', vars(new_child))

    def test_frozen_state(self):
        cfg = ConfigDict(nested={'beta': 12})
        cfg.freeze()
        value = self.roundtrip(cfg)
        self.assertIs(vars(value)['__frozen'], True)
        self.assertIs(vars(value.nested)['__frozen'], True)
        with self.assertRaises(KeyError):
            value.new_key = 7
        with self.assertRaises(KeyError):
            value.nested.new_key = 9
        value.nested.beta = 13
        self.assertEqual(value.nested.beta, 13)

    def test_unfreeze(self):
        cfg = ConfigDict(nested={'beta': 12})
        cfg.freeze()
        value = self.roundtrip(cfg)
        value.unfreeze()
        value.nested.added = 7
        self.assertEqual(value.nested.added, 7)
        self.assertIs(vars(value)['__frozen'], False)

    def test_missing_key_and_attribute(self):
        value = self.roundtrip(ConfigDict())
        with self.assertRaises(KeyError):
            value['absent']
        with self.assertRaises(AttributeError):
            value.absent
        self.assertFalse(value)

    def test_unknown_subclasses_and_mapping(self):
        class Unknown(ConfigDict):
            pass

        for value in (Unknown(), Dict(), type('UnknownMapping', (dict,), {})()):
            with self.subTest(type=type(value)):
                with self.assertRaisesRegex(ControlError, 'Unregistered dict subclass'):
                    ObjectEncoder().encode(value)

    def test_unsupported_dict_value(self):
        for value in (object(), lambda inp: inp):
            cfg = ConfigDict()
            cfg['unsupported'] = value
            with self.assertRaises(ControlError):
                ObjectEncoder().encode(cfg)

    def test_invalid_runtime_pin(self):
        changed = dict(adapter.PIN, addict='0.0.0')
        with self.assertRaises(ControlError):
            adapter.validate_class(ConfigDict, changed)


if __name__ == '__main__':
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized()
    OUT.mkdir(exist_ok=True)
    log = io.StringIO()
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(ConfigDictTests)
    case_names = [case.id().split('.')[-1] for case in tests]
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(tests)
    print(log.getvalue(), end='')
    report = {
        'total': result.testsRun,
        'passed': result.testsRun - len(result.failures) - len(result.errors),
        'success': result.wasSuccessful(),
        'cases': case_names,
        'cuda_initialized': torch.cuda.is_initialized(),
        'stdout': log.getvalue(),
    }
    (OUT / 'CONFIGDICT_UNIT_TESTS.json').write_text(json.dumps(report, indent=2))
    raise SystemExit(not (result.wasSuccessful() and not report['cuda_initialized']))
