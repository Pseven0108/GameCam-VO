"""Exact installed timm Format singleton adapter; no generic Enum admission."""
from enum import Enum
from importlib import import_module
from importlib.metadata import version
import inspect

from control_common import ControlError, file_sha

TAG = 'timm_format_enum_v1'
CLASS_KEY = 'timm.layers.format:Format'
MEMBERS = {'NCHW': 'NCHW', 'NHWC': 'NHWC', 'NCL': 'NCL', 'NLC': 'NLC'}
PIN = {
    'class': CLASS_KEY,
    'timm': '0.9.10',
    'source_sha256': '8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae',
}


def validate_class(cls, pin=PIN):
    if pin != PIN or cls.__module__ + ':' + cls.__qualname__ != CLASS_KEY:
        raise ControlError('Unsupported Format class or snapshot pin')
    installed = import_module('timm.layers.format').Format
    if cls is not installed or cls.__mro__ != (installed, str, Enum, object):
        raise ControlError('Format runtime class identity changed')
    if version('timm') != PIN['timm'] or file_sha(inspect.getsourcefile(cls)) != PIN['source_sha256']:
        raise ControlError('Format installed source/version changed')
    if set(cls.__members__) != set(MEMBERS):
        raise ControlError('Format member registry changed')
    for name, value in MEMBERS.items():
        member = cls.__members__[name]
        if type(member) is not cls or member.name != name or type(member.value) is not str or member.value != value:
            raise ControlError('Format member identity/value changed')


def encode_member(value):
    cls = type(value)
    validate_class(cls)
    if value.name not in MEMBERS or cls.__members__[value.name] is not value:
        raise ControlError('Unregistered Format member')
    return {'kind': TAG, 'class': CLASS_KEY, 'pin': dict(PIN),
            'member_name': value.name, 'member_value': value.value}


def restore_member(cls, node):
    if set(node) != {'kind', 'class', 'pin', 'member_name', 'member_value'} or node.get('kind') != TAG or node.get('class') != CLASS_KEY:
        raise ControlError('Incomplete or mismatched Format snapshot')
    validate_class(cls, node.get('pin'))
    name, value = node['member_name'], node['member_value']
    if type(name) is not str or type(value) is not str or name not in MEMBERS or MEMBERS[name] != value:
        raise ControlError('Unknown or mismatched Format member')
    member = cls.__members__[name]
    if type(member) is not cls or member.value != value or member.name != name:
        raise ControlError('Format member lookup changed')
    return member
