"""Minimal TFRecord/Example decoding using official wire schema, not TensorFlow."""
from __future__ import annotations

import struct

import numpy as np


def crc32c(data):
    table = []
    for number in range(256):
        value = number
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
        table.append(value)
    crc = 0xFFFFFFFF
    for value in data:
        crc = table[(crc ^ value) & 255] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def masked_crc(data):
    value = crc32c(data)
    return (((value >> 15) | (value << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def record_length(header):
    if len(header) != 12 or masked_crc(header[:8]) != struct.unpack("<I", header[8:])[0]:
        raise ValueError("TFRecord length CRC32C mismatch")
    length = struct.unpack("<Q", header[:8])[0]
    if length < 1 or length > 128*1024*1024:
        raise ValueError("First TFRecord exceeds the fixed per-sample acquisition bound")
    return length


def payload(record):
    length = record_length(record[:12])
    if len(record) != length+16:
        raise ValueError("Exact complete single-record fragment required")
    value = record[12:-4]
    if masked_crc(value) != struct.unpack("<I", record[-4:])[0]:
        raise ValueError("TFRecord payload CRC32C mismatch")
    return value


def example_class():
    # Field IDs and wire kinds are exactly tensorflow/core/example/{feature,
    # example}.proto. A separate descriptor pool needs no TensorFlow installation.
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    file = descriptor_pb2.FileDescriptorProto(name="phase5_example.proto", package="tensorflow", syntax="proto3")
    for name, field_type in (("BytesList", 12), ("FloatList", 2), ("Int64List", 3)):
        message = file.message_type.add(name=name)
        message.field.add(name="value", number=1, label=3, type=field_type)
    feature = file.message_type.add(name="Feature")
    feature.oneof_decl.add(name="kind")
    for index, (name, cls) in enumerate((("bytes_list", "BytesList"), ("float_list", "FloatList"), ("int64_list", "Int64List")), 1):
        feature.field.add(name=name, number=index, label=1, type=11, type_name=".tensorflow."+cls, oneof_index=0)
    features = file.message_type.add(name="Features")
    entry = features.nested_type.add(name="FeatureEntry")
    entry.options.map_entry = True
    entry.field.add(name="key", number=1, label=1, type=9)
    entry.field.add(name="value", number=2, label=1, type=11, type_name=".tensorflow.Feature")
    features.field.add(name="feature", number=1, label=3, type=11, type_name=".tensorflow.Features.FeatureEntry")
    message = file.message_type.add(name="Example")
    message.field.add(name="features", number=1, label=1, type=11, type_name=".tensorflow.Features")
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    descriptor = pool.FindMessageTypeByName("tensorflow.Example")
    return message_factory.GetMessageClass(descriptor)


def decode_features(record):
    message = example_class()()
    message.ParseFromString(payload(record))
    result = {}
    for name, feature in message.features.feature.items():
        kind = feature.WhichOneof("kind")
        if kind == "bytes_list":
            value = list(feature.bytes_list.value)
        elif kind == "float_list":
            value = np.asarray(feature.float_list.value, dtype=np.float32)
        elif kind == "int64_list":
            value = np.asarray(feature.int64_list.value, dtype=np.int64)
        else:
            raise ValueError("Unsupported or empty TF Example feature kind")
        result[name] = value
    if not result:
        raise ValueError("Empty TF Example")
    return result

