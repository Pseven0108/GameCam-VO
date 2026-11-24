"""Lossless adapter for the installed MMCV ConfigDict and its pinned Addict base."""
import inspect
from importlib import import_module
from importlib.metadata import version

from control_common import ControlError, file_sha


TAG = 'mmcv_configdict_mapping_v1'
CLASS_KEY = 'mmcv.utils.config:ConfigDict'
PIN = {
    'class': CLASS_KEY,
    'mmcv-full': '1.7.2',
    'mmcv_source_sha256': '02cb37945ed38c4cfcf606ae535369ca45abefb9ebffbee1a2b721c74d89d384',
    'addict': '2.4.0',
    'addict_source_sha256': '49c39f72568033bba0c99a17396d871cbf60097b7f5cf7be8b96d32e263cb9f5',
}


def validate_class(cls, pin=PIN):
    if pin != PIN or cls.__module__ + ':' + cls.__qualname__ != CLASS_KEY:
        raise ControlError('Unsupported ConfigDict class or snapshot pin')
    config_type = import_module('mmcv.utils.config').ConfigDict
    base = import_module('addict.addict').Dict
    if cls is not config_type or cls.__mro__ != (config_type, base, dict, object):
        raise ControlError('ConfigDict runtime class identity changed')
    if (version('mmcv-full') != PIN['mmcv-full']
            or version('addict') != PIN['addict']
            or file_sha(inspect.getsourcefile(config_type)) != PIN['mmcv_source_sha256']
            or file_sha(inspect.getsourcefile(base)) != PIN['addict_source_sha256']):
        raise ControlError('ConfigDict or Addict installed source/version changed')


def encode_mapping(value, encode):
    validate_class(type(value))
    return {
        'kind': TAG,
        'class': CLASS_KEY,
        'pin': dict(PIN),
        'items': [[encode(key), encode(item)] for key, item in dict.items(value)],
        'attrs': encode(vars(value)),
    }


def allocate(cls, node):
    validate_class(cls, node.get('pin'))
    if set(node) != {'kind', 'class', 'pin', 'items', 'attrs'}:
        raise ControlError('Incomplete ConfigDict snapshot')
    return dict.__new__(cls)


def hydrate(value, node, decode):
    # Addict.__setitem__ can update a parent and remove its own link fields.
    # Restore raw entries first and install the saved attribute mapping last.
    for key, item in node['items']:
        dict.__setitem__(value, decode(key), decode(item))
    attrs = decode(node['attrs'])
    if type(attrs) is not dict:
        raise ControlError('Invalid ConfigDict attribute mapping')
    object.__setattr__(value, '__dict__', attrs)
