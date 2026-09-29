"""
Drone log parsers.

Supports:
  - MAVLink telemetry logs (.tlog)
  - ArduPilot DataFlash binary logs (.bin)
  - ArduPilot text logs (.log)
  - Generic Type-Length-Value byte streams (.tlv)

All parsed data is normalized into a common dict-of-DataFrames schema with
these top-level keys (when available):
    position    -> timestamp, lat, lon, alt, relative_alt, vx, vy, vz, heading
    attitude    -> timestamp, roll, pitch, yaw (radians)
    vfr_hud     -> timestamp, throttle, airspeed, groundspeed, alt, climb
    battery     -> timestamp, voltage, current, remaining
    gps_raw     -> timestamp, fix_type, satellites, lat, lon, alt
    heartbeat   -> timestamp, base_mode, custom_mode, system_status
    _meta       -> dict with format name, message count, errors
"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Scalar primitives that show up inside VBAT struct schemas.
# Each entry maps the schema "type" string to a Python struct format char.
_VBAT_SCALAR_FMT: Dict[str, str] = {
    'double': 'd', 'single': 'f',
    'uint8': 'B',  'int8':   'b',
    'uint16': 'H', 'int16':  'h',
    'uint32': 'I', 'int32':  'i',
    'uint64': 'Q', 'int64':  'q',
}

try:
    from pymavlink import mavutil  # type: ignore
    HAS_PYMAVLINK = True
except ImportError:
    HAS_PYMAVLINK = False

# Safety caps to prevent runaway memory on malformed or huge files
MAX_MESSAGES = 2_000_000
MAX_TLV_RECORDS = 500_000
MAX_ERRORS_KEPT = 200


class DroneLogParser:
    """Routes to the right parser based on file extension."""

    def __init__(self, filepath: str):
        if not filepath or not isinstance(filepath, str):
            raise ValueError("filepath must be a non-empty string")
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {filepath}")
        if not path.is_file():
            raise ValueError(f"Not a file: {filepath}")

        self.filepath = str(path)
        self.ext = path.suffix.lower()
        self.data: Dict[str, Any] = {}
        self.errors: List[str] = []

    # ------------------------------------------------------------------
    def parse(self) -> Dict[str, Any]:
        """Dispatch to the correct parser for this file type."""
        try:
            if self.ext == '.tlog':
                self._parse_mavlink()
            elif self.ext in ('.bin', '.log'):
                self._parse_ardupilot()
            elif self.ext == '.tlv':
                self._parse_tlv()
            else:
                raise ValueError(f"Unsupported extension: {self.ext}")
        except (FileNotFoundError, PermissionError):
            raise
        except Exception as e:
            # Surface a clean error but include format info if we got that far
            raise RuntimeError(f"Parser failed for {self.ext}: {e}") from e
        return self.data

    # ------------------------------------------------------------------
    # MAVLink .tlog
    # ------------------------------------------------------------------
    def _parse_mavlink(self) -> None:
        if not HAS_PYMAVLINK:
            raise RuntimeError(
                "pymavlink is not installed. Run: pip install pymavlink"
            )

        try:
            mlog = mavutil.mavlink_connection(
                self.filepath, dialect='ardupilotmega', robust_parsing=True
            )
        except Exception as e:
            raise RuntimeError(f"Cannot open MAVLink log: {e}") from e

        records: Dict[str, List[Dict[str, Any]]] = {
            'position': [], 'attitude': [], 'vfr_hud': [],
            'battery': [], 'gps_raw': [], 'heartbeat': [], 'sys_status': [],
        }
        msg_types_seen: Dict[str, int] = {}
        total = 0
        capped = False

        while total < MAX_MESSAGES:
            try:
                msg = mlog.recv_match(blocking=False)
            except Exception as e:
                self._record_error(f"recv error after {total} msgs: {e}")
                break

            if msg is None:
                break

            total += 1
            try:
                mtype = msg.get_type()
            except Exception:
                continue

            msg_types_seen[mtype] = msg_types_seen.get(mtype, 0) + 1
            ts = getattr(msg, '_timestamp', None)

            try:
                self._handle_mavlink_message(msg, mtype, ts, records)
            except Exception as e:
                self._record_error(f"{mtype}: {e}")

        if total >= MAX_MESSAGES:
            capped = True
            self._record_error(
                f"Message limit ({MAX_MESSAGES:,}) reached; remainder skipped."
            )

        # Fallback: promote SYS_STATUS if BATTERY_STATUS empty
        if not records['battery'] and records['sys_status']:
            records['battery'] = [
                {k: r.get(k) for k in ('timestamp', 'voltage', 'current', 'remaining')}
                for r in records['sys_status']
            ]

        self._finalize_dataframes(records)
        self.data['_meta'] = {
            'format': 'MAVLink .tlog',
            'total_messages': total,
            'message_types': msg_types_seen,
            'errors': self.errors,
            'capped': capped,
        }

    def _handle_mavlink_message(self, msg, mtype, ts, records):
        if mtype == 'GLOBAL_POSITION_INT':
            records['position'].append({
                'timestamp': ts,
                'lat': msg.lat / 1e7,
                'lon': msg.lon / 1e7,
                'alt': msg.alt / 1000.0,
                'relative_alt': msg.relative_alt / 1000.0,
                'vx': msg.vx / 100.0,
                'vy': msg.vy / 100.0,
                'vz': msg.vz / 100.0,
                'heading': msg.hdg / 100.0 if msg.hdg != 65535 else None,
            })
        elif mtype == 'ATTITUDE':
            records['attitude'].append({
                'timestamp': ts,
                'roll': float(msg.roll),
                'pitch': float(msg.pitch),
                'yaw': float(msg.yaw),
                'rollspeed': float(msg.rollspeed),
                'pitchspeed': float(msg.pitchspeed),
                'yawspeed': float(msg.yawspeed),
            })
        elif mtype == 'VFR_HUD':
            records['vfr_hud'].append({
                'timestamp': ts,
                'airspeed': float(msg.airspeed),
                'groundspeed': float(msg.groundspeed),
                'heading': int(msg.heading),
                'throttle': int(msg.throttle),
                'alt': float(msg.alt),
                'climb': float(msg.climb),
            })
        elif mtype == 'BATTERY_STATUS':
            voltages = [v for v in msg.voltages if v != 65535]
            records['battery'].append({
                'timestamp': ts,
                'voltage': sum(voltages) / 1000.0 if voltages else None,
                'current': (msg.current_battery / 100.0
                            if msg.current_battery != -1 else None),
                'remaining': (msg.battery_remaining
                              if msg.battery_remaining != -1 else None),
            })
        elif mtype == 'GPS_RAW_INT':
            records['gps_raw'].append({
                'timestamp': ts,
                'fix_type': msg.fix_type,
                'satellites': msg.satellites_visible,
                'lat': msg.lat / 1e7,
                'lon': msg.lon / 1e7,
                'alt': msg.alt / 1000.0,
            })
        elif mtype == 'SYS_STATUS':
            records['sys_status'].append({
                'timestamp': ts,
                'voltage': msg.voltage_battery / 1000.0,
                'current': (msg.current_battery / 100.0
                            if msg.current_battery != -1 else None),
                'remaining': (msg.battery_remaining
                              if msg.battery_remaining != -1 else None),
                'load_pct': msg.load / 10.0,
            })
        elif mtype == 'HEARTBEAT':
            records['heartbeat'].append({
                'timestamp': ts,
                'type': msg.type,
                'autopilot': msg.autopilot,
                'base_mode': msg.base_mode,
                'custom_mode': msg.custom_mode,
                'system_status': msg.system_status,
            })

    # ------------------------------------------------------------------
    # ArduPilot DataFlash .bin / .log
    # ------------------------------------------------------------------
    def _parse_ardupilot(self) -> None:
        if not HAS_PYMAVLINK:
            raise RuntimeError(
                "pymavlink is not installed. Run: pip install pymavlink"
            )

        try:
            mlog = mavutil.mavlink_connection(
                self.filepath, dialect='ardupilotmega', robust_parsing=True
            )
        except Exception as e:
            raise RuntimeError(f"Cannot open ArduPilot log: {e}") from e

        raw: Dict[str, List[Dict[str, Any]]] = {}
        msg_types_seen: Dict[str, int] = {}
        total = 0
        capped = False

        # Metadata messages we want to skip (they don't carry telemetry)
        skip_types = {'FMT', 'FMTU', 'UNIT', 'MULT', 'PARM', 'MSG'}

        while total < MAX_MESSAGES:
            try:
                msg = mlog.recv_match(blocking=False)
            except Exception as e:
                self._record_error(f"recv error after {total} msgs: {e}")
                break

            if msg is None:
                break

            total += 1
            try:
                mtype = msg.get_type()
            except Exception:
                continue

            msg_types_seen[mtype] = msg_types_seen.get(mtype, 0) + 1
            if mtype in skip_types:
                continue

            try:
                d = msg.to_dict()
                d['_timestamp'] = getattr(msg, '_timestamp', None)
                raw.setdefault(mtype, []).append(d)
            except Exception as e:
                self._record_error(f"{mtype}: {e}")

        if total >= MAX_MESSAGES:
            capped = True
            self._record_error(
                f"Message limit ({MAX_MESSAGES:,}) reached; remainder skipped."
            )

        # Store every native message type as its own DataFrame
        for mtype, rows in raw.items():
            try:
                if rows:
                    self.data[mtype] = pd.DataFrame(rows)
            except Exception as e:
                self._record_error(f"DataFrame build {mtype}: {e}")

        # Map to common schema
        self._normalize_ardupilot()

        self.data['_meta'] = {
            'format': 'ArduPilot DataFlash',
            'total_messages': total,
            'message_types': msg_types_seen,
            'errors': self.errors,
            'capped': capped,
        }

    def _normalize_ardupilot(self) -> None:
        """Map ArduPilot DataFlash schema -> common schema used by viz layer."""

        def add_time_cols(df: pd.DataFrame) -> pd.DataFrame:
            if df is None or df.empty:
                return df
            if '_timestamp' in df.columns:
                df = df.rename(columns={'_timestamp': 'timestamp'})
            if 'timestamp' in df.columns:
                ts_series = pd.to_numeric(df['timestamp'], errors='coerce')
                df['timestamp'] = ts_series
                valid = ts_series.dropna()
                if not valid.empty:
                    t0 = valid.iloc[0]
                    df['elapsed'] = ts_series - t0
                    df['datetime'] = pd.to_datetime(
                        ts_series, unit='s', errors='coerce'
                    )
            return df

        try:
            # GPS -> position
            if 'GPS' in self.data and not self.data['GPS'].empty:
                g = self.data['GPS']
                pos = pd.DataFrame({
                    '_timestamp': g.get('_timestamp'),
                    'lat': g.get('Lat'),
                    'lon': g.get('Lng'),
                    'alt': g.get('Alt'),
                    'satellites': g.get('NSats'),
                    'fix_type': g.get('Status'),
                })
                self.data['position'] = add_time_cols(pos)
        except Exception as e:
            self._record_error(f"normalize GPS: {e}")

        try:
            if 'ATT' in self.data and not self.data['ATT'].empty:
                a = self.data['ATT']
                # ArduPilot stores attitude in degrees; convert to radians
                # for consistency with MAVLink schema
                roll = pd.to_numeric(a.get('Roll'), errors='coerce')
                pitch = pd.to_numeric(a.get('Pitch'), errors='coerce')
                yaw = pd.to_numeric(a.get('Yaw'), errors='coerce')
                att = pd.DataFrame({
                    '_timestamp': a.get('_timestamp'),
                    'roll': np.radians(roll) if roll is not None else None,
                    'pitch': np.radians(pitch) if pitch is not None else None,
                    'yaw': np.radians(yaw) if yaw is not None else None,
                })
                self.data['attitude'] = add_time_cols(att)
        except Exception as e:
            self._record_error(f"normalize ATT: {e}")

        try:
            if 'CTUN' in self.data and not self.data['CTUN'].empty:
                c = self.data['CTUN']
                throttle = pd.to_numeric(c.get('ThO'), errors='coerce')
                if throttle is not None:
                    throttle = throttle * 100.0  # 0-1 → percentage
                vfr = pd.DataFrame({
                    '_timestamp': c.get('_timestamp'),
                    'throttle': throttle,
                    'alt': c.get('Alt'),
                    'climb': c.get('CRt'),
                })
                self.data['vfr_hud'] = add_time_cols(vfr)
        except Exception as e:
            self._record_error(f"normalize CTUN: {e}")

        try:
            if 'BAT' in self.data and not self.data['BAT'].empty:
                b = self.data['BAT']
                bat = pd.DataFrame({
                    '_timestamp': b.get('_timestamp'),
                    'voltage': b.get('Volt'),
                    'current': b.get('Curr'),
                    'remaining': b.get('RemPct'),
                })
                self.data['battery'] = add_time_cols(bat)
        except Exception as e:
            self._record_error(f"normalize BAT: {e}")

        # Apply time columns to every raw frame too (for Raw Data tab)
        for k in list(self.data.keys()):
            if isinstance(self.data.get(k), pd.DataFrame):
                try:
                    self.data[k] = add_time_cols(self.data[k])
                except Exception as e:
                    self._record_error(f"time cols {k}: {e}")

    # ------------------------------------------------------------------
    # TLV dispatcher — picks VBAT (Martin UAV V-BAT / VectorNav) vs generic
    # ------------------------------------------------------------------
    def _parse_tlv(self) -> None:
        try:
            with open(self.filepath, 'rb') as f:
                data = f.read()
        except (OSError, PermissionError) as e:
            raise RuntimeError(f"Cannot read TLV file: {e}") from e

        # VBAT-style logs open with a "SESS" magic block followed by a JSON
        # session header. Auto-detect and dispatch.
        if len(data) >= 8 and data[:4] == b'SESS':
            try:
                self._parse_vbat_tlv(data)
                return
            except Exception as e:
                # Fall through to the generic byte-level parse so the user can
                # still inspect raw records, but surface the failure.
                self._record_error(
                    f"VBAT TLV parse failed ({e}); using generic fallback."
                )

        self._parse_generic_tlv(data)

    # ------------------------------------------------------------------
    # Generic TLV (1-byte type, 2-byte LE length, N-byte value)
    # ------------------------------------------------------------------
    def _parse_generic_tlv(self, data: bytes) -> None:
        records: List[Dict[str, Any]] = []
        offset = 0
        size = len(data)

        while offset + 3 <= size and len(records) < MAX_TLV_RECORDS:
            try:
                t = data[offset]
                length = struct.unpack('<H', data[offset + 1:offset + 3])[0]
                if length > size or offset + 3 + length > size:
                    self._record_error(
                        f"Truncated TLV at offset {offset} (length={length})"
                    )
                    break
                value = data[offset + 3:offset + 3 + length]
                records.append({
                    'offset': offset,
                    'type': t,
                    'type_hex': f'0x{t:02X}',
                    'length': length,
                    'value_hex': value[:64].hex(),
                })
                offset += 3 + length
            except Exception as e:
                self._record_error(f"TLV parse at {offset}: {e}")
                break

        capped = len(records) >= MAX_TLV_RECORDS
        if capped:
            self._record_error(
                f"TLV record limit ({MAX_TLV_RECORDS:,}) reached; remainder skipped."
            )

        try:
            self.data['tlv_records'] = pd.DataFrame(records)
        except Exception as e:
            self._record_error(f"DataFrame build: {e}")
            self.data['tlv_records'] = pd.DataFrame()

        self.data['_meta'] = {
            'format': 'Generic TLV',
            'total_messages': len(records),
            'errors': self.errors,
            'capped': capped,
            'note': 'Generic byte-level parse. Vendor decoders can be plugged in.',
        }

    # ------------------------------------------------------------------
    # VBAT TLV (Martin UAV V-BAT / VectorNav INS)
    # ------------------------------------------------------------------
    # Format:
    #   [SESS][4-byte LE length][JSON session header]
    #   [META][4-byte LE length][JSON schema describing every track]
    #   then a stream of records:
    #     [4-byte tag][payload of `size` bytes per the matching track schema]
    # Variable-length tracks (type == "log" or "point_cloud_packet") are not
    # decoded — the parser resyncs forward to the next known struct tag.
    # ------------------------------------------------------------------
    def _parse_vbat_tlv(self, data: bytes) -> None:
        size = len(data)
        pos = 0

        # ----- SESS header -----
        if size < 8 or data[:4] != b'SESS':
            raise RuntimeError("Missing SESS magic")
        sess_len = struct.unpack('<I', data[4:8])[0]
        if 8 + sess_len > size:
            raise RuntimeError(f"SESS length {sess_len} exceeds file")
        try:
            session = json.loads(data[8:8 + sess_len].decode('utf-8', errors='replace'))
        except Exception as e:
            session = {}
            self._record_error(f"SESS JSON parse: {e}")
        pos = 8 + sess_len

        # ----- META header -----
        if pos + 8 > size or data[pos:pos + 4] != b'META':
            raise RuntimeError(f"Missing META magic at offset {pos}")
        meta_len = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        if pos + 8 + meta_len > size:
            raise RuntimeError(f"META length {meta_len} exceeds file")
        try:
            meta_doc = json.loads(
                data[pos + 8:pos + 8 + meta_len].decode('utf-8', errors='replace')
            )
        except Exception as e:
            raise RuntimeError(f"META JSON parse failed: {e}") from e
        pos += 8 + meta_len

        tracks: Dict[str, dict] = meta_doc.get('tracks', {}) or {}
        # Index struct tracks by their 4-byte tag (as bytes) for fast lookup.
        struct_tags: Dict[bytes, dict] = {}
        for tag, spec in tracks.items():
            if (
                isinstance(tag, str)
                and len(tag.encode('ascii', 'replace')) == 4
                and isinstance(spec, dict)
                and spec.get('type') == 'struct'
                and 'size' in spec
                and 'entries' in spec
            ):
                struct_tags[tag.encode('ascii')] = spec

        if not struct_tags:
            raise RuntimeError("META schema has no struct tracks")

        # ----- record stream -----
        records_by_track: Dict[str, List[Dict[str, Any]]] = {}
        msg_types_seen: Dict[str, int] = {}
        total = 0
        capped = False
        consecutive_skips = 0

        while pos + 4 <= size and total < MAX_MESSAGES:
            tag = data[pos:pos + 4]
            spec = struct_tags.get(tag)
            if spec is None:
                # Resync: advance one byte and keep scanning. This handles
                # unknown variable-length records that we don't decode.
                pos += 1
                consecutive_skips += 1
                if consecutive_skips > 1_000_000:
                    self._record_error(
                        f"Lost sync after offset {pos}; aborting record scan."
                    )
                    break
                continue

            consecutive_skips = 0
            tsize = int(spec['size'])
            if pos + 4 + tsize > size:
                # Truncated final record; stop cleanly.
                break

            payload = data[pos + 4:pos + 4 + tsize]
            tag_str = tag.decode('ascii')
            try:
                record = self._unpack_vbat_struct(payload, spec.get('entries', []))
                records_by_track.setdefault(tag_str, []).append(record)
            except Exception as e:
                if len(self.errors) < MAX_ERRORS_KEPT:
                    self._record_error(f"{tag_str}: {e}")
            msg_types_seen[tag_str] = msg_types_seen.get(tag_str, 0) + 1
            total += 1
            pos += 4 + tsize

        if total >= MAX_MESSAGES:
            capped = True
            self._record_error(
                f"VBAT record limit ({MAX_MESSAGES:,}) reached; remainder skipped."
            )

        # Build dataframes for every track we collected.
        for tag, rows in records_by_track.items():
            try:
                df = pd.DataFrame(rows)
                if 'linux_time' in df.columns:
                    ts = pd.to_numeric(df['linux_time'], errors='coerce')
                    df['timestamp'] = ts
                    valid = ts.dropna()
                    if not valid.empty:
                        t0 = valid.iloc[0]
                        df['elapsed'] = ts - t0
                        df['datetime'] = pd.to_datetime(
                            ts, unit='s', errors='coerce'
                        )
                self.data[tag] = df
            except Exception as e:
                self._record_error(f"VBAT DataFrame build {tag}: {e}")

        # Map VBAT track frames onto the app's common schema.
        self._normalize_vbat()

        vessel = session.get('Vessel') if isinstance(session, dict) else None
        self.data['_meta'] = {
            'format': f"VBAT TLV ({vessel})" if vessel else "VBAT TLV",
            'total_messages': total,
            'message_types': msg_types_seen,
            'errors': self.errors,
            'capped': capped,
            'session': session,
            'note': 'Martin UAV V-BAT / VectorNav structured log.',
        }

    # ------------------------------------------------------------------
    def _unpack_vbat_struct(
        self, buf: bytes, entries: List[dict], prefix: str = ''
    ) -> Dict[str, Any]:
        """Flatten the VBAT entry list into {name: value}.

        Top-level fields use the schema's 'name' (so the normalizer can find
        things like 'linux_time' and 'pos_Lat'). Nested struct fields are
        prefixed with their parent's name so identical sub-fields like x/y/z
        from multiple nested structs don't collide.
        """
        out: Dict[str, Any] = {}
        off = 0
        for entry in entries:
            etype = entry.get('type')
            esize = int(entry.get('size', 0))
            # Prefer schema 'name' (stable, used by the normalizer). Fall back
            # to 'varname' only when name is missing.
            ename = entry.get('name') or entry.get('varname') or ''
            field = f"{prefix}{ename}" if prefix else ename

            if etype == 'struct':
                sub_entries = entry.get('entries') or []
                # Prefix nested fields with parent name to avoid collisions
                # among repeated sub-structs (each carrying x/y/z, etc.).
                sub_prefix = f"{field}_" if field else prefix
                sub_out = self._unpack_vbat_struct(
                    buf[off:off + esize], sub_entries, prefix=sub_prefix
                )
                out.update(sub_out)
            elif etype in _VBAT_SCALAR_FMT:
                fmt = '<' + _VBAT_SCALAR_FMT[etype]
                try:
                    out[field] = struct.unpack_from(fmt, buf, off)[0]
                except struct.error:
                    out[field] = None
            # else: unknown type — skip the bytes silently.
            off += esize
        return out

    # ------------------------------------------------------------------
    def _normalize_vbat(self) -> None:
        """Project VBAT track frames onto the common position/attitude/
        vfr_hud/gps_raw schema so the existing chart/map layer just works."""

        def _series(src: pd.DataFrame, col: str) -> pd.Series:
            """Always returns a numeric Series of the same length as src,
            even when the column is missing or returns a scalar."""
            val = src.get(col) if isinstance(src, pd.DataFrame) else None
            if val is None or not isinstance(val, pd.Series):
                return pd.Series([np.nan] * len(src), index=src.index)
            return pd.to_numeric(val, errors='coerce')

        def _with_time_cols(df: pd.DataFrame, ts: pd.Series) -> pd.DataFrame:
            df = df.copy()
            if not isinstance(ts, pd.Series):
                ts = pd.Series([np.nan] * len(df), index=df.index)
            df['timestamp'] = ts
            valid = ts.dropna()
            if not valid.empty:
                t0 = valid.iloc[0]
                df['elapsed'] = ts - t0
                df['datetime'] = pd.to_datetime(ts, unit='s', errors='coerce')
            return df

        # ---- VN2a → position + attitude + vfr_hud (primary INS) ----
        vn2a = self.data.get('VN2a')
        if isinstance(vn2a, pd.DataFrame) and not vn2a.empty:
            try:
                ts        = _series(vn2a, 'linux_time')
                lat       = _series(vn2a, 'pos_Lat')
                lon       = _series(vn2a, 'pos_Lon')
                alt       = _series(vn2a, 'pos_Alt')
                vN        = _series(vn2a, 'vel_N')
                vE        = _series(vn2a, 'vel_E')
                vD        = _series(vn2a, 'vel_D')
                yaw_deg   = _series(vn2a, 'ypr_0')
                pitch_deg = _series(vn2a, 'ypr_1')
                roll_deg  = _series(vn2a, 'ypr_2')

                self.data['position'] = _with_time_cols(pd.DataFrame({
                    'lat': lat, 'lon': lon, 'alt': alt,
                    'vx': vN, 'vy': vE, 'vz': vD,
                    'heading': yaw_deg,
                }), ts)

                # VectorNav YPR are degrees; the chart layer expects radians.
                self.data['attitude'] = _with_time_cols(pd.DataFrame({
                    'yaw': np.radians(yaw_deg),
                    'pitch': np.radians(pitch_deg),
                    'roll': np.radians(roll_deg),
                }), ts)

                groundspeed = np.sqrt(vN.fillna(0) ** 2 + vE.fillna(0) ** 2)
                groundspeed[vN.isna() & vE.isna()] = np.nan
                climb = -vD  # NED → +up
                self.data['vfr_hud'] = _with_time_cols(pd.DataFrame({
                    'alt': alt,
                    'groundspeed': groundspeed,
                    'climb': climb,
                }), ts)
            except Exception as e:
                self._record_error(f"normalize VN2a: {e}")

        # ---- VN2b → gps_raw (independent GPS measurement) ----
        vn2b = self.data.get('VN2b')
        if isinstance(vn2b, pd.DataFrame) and not vn2b.empty:
            try:
                ts = _series(vn2b, 'linux_time')
                self.data['gps_raw'] = _with_time_cols(pd.DataFrame({
                    'lat':        _series(vn2b, 'GPS1pos_Lat'),
                    'lon':        _series(vn2b, 'GPS1pos_Lon'),
                    'alt':        _series(vn2b, 'GPS1pos_Alt'),
                    'fix_type':   _series(vn2b, 'GPS1Fix'),
                    'satellites': _series(vn2b, 'numGPS1Sats'),
                }), ts)
            except Exception as e:
                self._record_error(f"normalize VN2b: {e}")

        # ---- Fall back to GPSa or VN2b for position when VN2a is missing ----
        if 'position' not in self.data or (
            isinstance(self.data.get('position'), pd.DataFrame)
            and self.data['position'].empty
        ):
            vn2b = self.data.get('VN2b')
            if isinstance(vn2b, pd.DataFrame) and not vn2b.empty:
                try:
                    ts = _series(vn2b, 'linux_time')
                    self.data['position'] = _with_time_cols(pd.DataFrame({
                        'lat': _series(vn2b, 'GPS1pos_Lat'),
                        'lon': _series(vn2b, 'GPS1pos_Lon'),
                        'alt': _series(vn2b, 'GPS1pos_Alt'),
                        'vx':  _series(vn2b, 'GPS1vel_N'),
                        'vy':  _series(vn2b, 'GPS1vel_E'),
                        'vz':  _series(vn2b, 'GPS1vel_D'),
                    }), ts)
                except Exception as e:
                    self._record_error(f"normalize VN2b->position: {e}")

    # ------------------------------------------------------------------
    def _finalize_dataframes(self, records: Dict[str, List[Dict[str, Any]]]):
        """Convert lists-of-dicts to DataFrames, add elapsed/datetime cols."""
        for key, rows in records.items():
            if not rows:
                self.data[key] = pd.DataFrame()
                continue
            try:
                df = pd.DataFrame(rows)
                if 'timestamp' in df.columns:
                    ts = pd.to_numeric(df['timestamp'], errors='coerce')
                    df['timestamp'] = ts
                    valid = ts.dropna()
                    if not valid.empty:
                        t0 = valid.iloc[0]
                        df['elapsed'] = ts - t0
                        df['datetime'] = pd.to_datetime(
                            ts, unit='s', errors='coerce'
                        )
                self.data[key] = df
            except Exception as e:
                self._record_error(f"finalize {key}: {e}")
                self.data[key] = pd.DataFrame()

    def _record_error(self, msg: str) -> None:
        """Append an error, capping the list to keep memory sane."""
        if len(self.errors) < MAX_ERRORS_KEPT:
            self.errors.append(msg)
        elif len(self.errors) == MAX_ERRORS_KEPT:
            self.errors.append(
                f"... further errors suppressed after {MAX_ERRORS_KEPT}"
            )
