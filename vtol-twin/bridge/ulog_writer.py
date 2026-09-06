"""Minimal PX4 ULog writer (file format v1) - enough for pyulog to read what we write.

Layout: 16-byte header, flag-bits message, format definitions, info messages, then per-topic
subscriptions (A) followed by data messages (D). All integers little-endian, no implicit padding.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Sequence, Tuple

MAGIC = b"\x55\x4c\x6f\x67\x01\x12\x35"
VERSION = 1
_TYPES = {  # ulog type -> struct code
    "int8_t": "b", "uint8_t": "B", "int16_t": "h", "uint16_t": "H", "int32_t": "i", "uint32_t": "I",
    "int64_t": "q", "uint64_t": "Q", "float": "f", "double": "d", "bool": "?", "char": "c",
}


def _msg(msg_type: bytes, payload: bytes) -> bytes:
    return struct.pack("<HB", len(payload), msg_type[0]) + payload


class Topic:
    """A ULog message format: name + ordered (type, field[, array_len]) definitions."""

    def __init__(self, name: str, fields: Sequence[Tuple[str, str]]):
        self.name = name
        self.fields: List[Tuple[str, str, int]] = []
        fmt = "<"
        for typ, fname in fields:
            arr = 1
            if "[" in typ:
                typ, n = typ[:-1].split("[")
                arr = int(n)
            self.fields.append((typ, fname, arr))
            fmt += _TYPES[typ] * arr
        self.struct = struct.Struct(fmt)
        assert self.fields[0][1] == "timestamp" and self.fields[0][0] == "uint64_t", "timestamp must come first"

    def definition(self) -> str:
        parts = [f"{t}[{n}] {f}" if n > 1 else f"{t} {f}" for t, f, n in self.fields]
        return f"{self.name}:" + ";".join(parts) + ";"

    def pack(self, row: Dict[str, Any]) -> bytes:
        values: List[Any] = []
        for typ, fname, arr in self.fields:
            v = row.get(fname, 0)
            if arr > 1:
                seq = list(v) if isinstance(v, (list, tuple)) else [v] * arr
                seq = (seq + [0] * arr)[:arr]
                values.extend(self._coerce(typ, x) for x in seq)
            else:
                values.append(self._coerce(typ, v))
        return self.struct.pack(*values)

    @staticmethod
    def _coerce(typ: str, v: Any) -> Any:
        if typ == "bool":
            return bool(v)
        if typ == "char":
            return (v if isinstance(v, bytes) else str(v).encode())[:1] or b"\x00"
        if typ in ("float", "double"):
            return float(v)
        return int(v)


class ULogWriter:
    def __init__(self, path: str, start_timestamp_us: int, info: Dict[str, Any] | None = None,
                 params: Dict[str, Any] | None = None):
        self._f = open(path, "wb")
        self._f.write(MAGIC + struct.pack("<B", VERSION) + struct.pack("<Q", start_timestamp_us))
        self._f.write(_msg(b"B", bytes(8) + bytes(8) + bytes(24)))           # flag bits: nothing special
        self._topics: Dict[str, Topic] = {}
        self._msg_ids: Dict[str, int] = {}
        self._pending_info = dict(info or {})
        self._pending_params = dict(params or {})
        self._data_started = False

    def add_topic(self, topic: Topic) -> None:
        assert not self._data_started, "formats must be declared before data"
        self._topics[topic.name] = topic
        self._f.write(_msg(b"F", topic.definition().encode()))

    def _write_info(self) -> None:
        for key, value in self._pending_info.items():
            if isinstance(value, str):
                b = value.encode()
                type_key = f"char[{len(b)}] {key}".encode()
                self._f.write(_msg(b"I", struct.pack("<B", len(type_key)) + type_key + b))
            elif isinstance(value, float):
                type_key = f"double {key}".encode()
                self._f.write(_msg(b"I", struct.pack("<B", len(type_key)) + type_key + struct.pack("<d", value)))
            else:
                type_key = f"uint64_t {key}".encode() if int(value) >= 0 else f"int64_t {key}".encode()
                self._f.write(_msg(b"I", struct.pack("<B", len(type_key)) + type_key + struct.pack("<q", int(value))))
        for key, value in self._pending_params.items():
            if isinstance(value, float):
                type_key = f"float {key}".encode()
                self._f.write(_msg(b"P", struct.pack("<B", len(type_key)) + type_key + struct.pack("<f", value)))
            else:
                type_key = f"int32_t {key}".encode()
                self._f.write(_msg(b"P", struct.pack("<B", len(type_key)) + type_key + struct.pack("<i", int(value))))

    def _start_data(self) -> None:
        self._write_info()
        for i, name in enumerate(self._topics):
            self._msg_ids[name] = i
            self._f.write(_msg(b"A", struct.pack("<BH", 0, i) + name.encode()))
        self._data_started = True

    def write(self, topic_name: str, row: Dict[str, Any]) -> None:
        if not self._data_started:
            self._start_data()
        topic = self._topics[topic_name]
        self._f.write(_msg(b"D", struct.pack("<H", self._msg_ids[topic_name]) + topic.pack(row)))

    def close(self) -> None:
        if not self._data_started:
            self._start_data()
        self._f.close()

    def __enter__(self) -> "ULogWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
