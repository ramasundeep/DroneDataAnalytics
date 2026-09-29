"""
Drone Data Analytics — Streamlit app.

Run on Windows:
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import traceback
from pathlib import Path

import pandas as pd
import streamlit as st

from parsers import DroneLogParser
from utils import format_size, validate_file
from visualizations import (
    build_flight_map,
    compute_flight_stats,
    plot_altitude,
    plot_attitude,
    plot_battery,
    plot_throttle_speed,
)

# streamlit-folium is the only dependency that fails noisily if missing on Windows.
# Wrap the import so the app still loads and shows a clear message.
try:
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

st.set_page_config(
    page_title="Drone Analytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    section[data-testid="stSidebar"] { background-color: #161a23; }
    div[data-testid="stMetric"] {
        background: #1c1f26;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        border: 1px solid #2a2f3a;
    }
    div[data-testid="stMetricLabel"] {
        color: #8b92a3;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] {
        color: #fafafa;
        font-size: 1.35rem;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2a2f3a; }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 0;
        padding: 0.55rem 1rem;
        color: #8b92a3;
        font-size: 0.88rem;
    }
    .stTabs [aria-selected="true"] {
        color: #fafafa;
        border-bottom: 2px solid #4ecdc4;
    }
    h1 { font-size: 1.6rem; font-weight: 500; letter-spacing: -0.01em; }
    h2, h3 { color: #fafafa; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Cached parse — keyed by file hash so re-uploads of the same file are instant
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=4)
def parse_log_cached(filepath: str, file_hash: str):
    parser = DroneLogParser(filepath)
    data = parser.parse()
    return data, parser.errors


# ----------------------------------------------------------------------
# Main app
# ----------------------------------------------------------------------
def main():
    st.title("Drone Data Analytics")
    st.caption("Parse and visualize ArduPilot, PX4, and MAVLink flight logs")

    with st.sidebar:
        st.subheader("Log file")
        uploaded = st.file_uploader(
            "Select drone log",
            type=['tlog', 'bin', 'log', 'tlv'],
            help="MAVLink .tlog · ArduPilot .bin/.log · Generic .tlv",
        )
        st.markdown("---")
        with st.expander("Supported formats", expanded=False):
            st.markdown(
                "- **`.tlog`** — MAVLink telemetry log (ground station)\n"
                "- **`.bin`** — ArduPilot DataFlash binary\n"
                "- **`.log`** — ArduPilot text log\n"
                "- **`.tlv`** — Generic Type-Length-Value\n"
            )
        with st.expander("Roadmap", expanded=False):
            st.markdown(
                "- Video stream sync (companion MP4/MKV)\n"
                "- ULog (.ulg) for pure PX4\n"
                "- Anomaly detection on flight parameters"
            )

    if uploaded is None:
        _render_landing()
        return

    valid, msg = validate_file(uploaded, uploaded.name)
    if not valid:
        st.sidebar.error(msg)
        st.error(f"**Invalid file** — {msg}")
        return

    st.sidebar.success(f"Loaded: `{uploaded.name}`")
    st.sidebar.caption(
        f"Size: {format_size(uploaded.size)} · "
        f"Type: `{Path(uploaded.name).suffix.lower()}`"
    )
    if msg and 'warning' in msg.lower():
        st.sidebar.warning(msg)

    # Persist to a temp file. tempfile handles the OS-specific temp dir.
    try:
        file_bytes = uploaded.getvalue()
    except Exception as e:
        st.error(f"Could not read uploaded bytes: {e}")
        return

    file_hash = hashlib.sha1(file_bytes).hexdigest()
    suffix = Path(uploaded.name).suffix

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
    except OSError as e:
        st.error(f"Could not write temp file: {e}")
        return

    try:
        with st.spinner(f"Parsing {uploaded.name}..."):
            try:
                data, errors = parse_log_cached(tmp_path, file_hash)
            except (FileNotFoundError, PermissionError) as e:
                st.error(f"**File access error** — {e}")
                return
            except RuntimeError as e:
                st.error(f"**Parse failed** — {e}")
                with st.expander("Show traceback"):
                    st.code(traceback.format_exc())
                return
            except Exception as e:
                st.error(f"**Unexpected error** — {type(e).__name__}: {e}")
                with st.expander("Show traceback"):
                    st.code(traceback.format_exc())
                return

        _render_overview(data)

        if data.get('_meta', {}).get('capped'):
            st.warning(
                "Parse hit the message limit — only the first portion of the "
                "log is shown. Split very large logs before uploading."
            )

        if errors:
            with st.expander(f"{len(errors)} parser warnings"):
                for err in errors[:50]:
                    st.text(f"• {err}")
                if len(errors) > 50:
                    st.text(f"… and {len(errors) - 50} more")

        tab_series, tab_map, tab_raw, tab_info = st.tabs([
            "Time Series", "Flight Map", "Raw Data", "Info"
        ])
        with tab_series:
            _safe_render(_render_time_series, data, "Time Series")
        with tab_map:
            _safe_render(_render_map, data, "Flight Map")
        with tab_raw:
            _safe_render(_render_raw_data, data, "Raw Data")
        with tab_info:
            _safe_render(_render_info, data, "Info")

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # Windows may hold the lock briefly; cache cleanup will get it


# ----------------------------------------------------------------------
# Per-tab error boundary
# ----------------------------------------------------------------------
def _safe_render(fn, data, tab_name: str):
    try:
        fn(data)
    except Exception as e:
        st.error(f"**{tab_name} tab failed** — {type(e).__name__}: {e}")
        with st.expander("Show traceback"):
            st.code(traceback.format_exc())


# ----------------------------------------------------------------------
# UI sections
# ----------------------------------------------------------------------
def _render_landing():
    st.info("Upload a drone log file from the sidebar to begin.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "##### Time Series\n"
            "Throttle, attitude, altitude, battery — all interactive."
        )
    with col2:
        st.markdown(
            "##### Flight Map\n"
            "GPS path with altitude-graded color and start/end markers."
        )
    with col3:
        st.markdown(
            "##### Raw Data\n"
            "Inspect every parsed message type, export to CSV."
        )


def _render_overview(data: dict):
    meta = data.get('_meta', {}) if isinstance(data, dict) else {}
    cols = st.columns(4)
    cols[0].metric("Format", meta.get('format', 'Unknown'))
    cols[1].metric("Messages", f"{meta.get('total_messages', 0):,}")

    pos = data.get('position', pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
    if isinstance(pos, pd.DataFrame) and not pos.empty and \
       'elapsed' in pos.columns and pos['elapsed'].notna().any():
        cols[2].metric("Duration", f"{pos['elapsed'].max():.1f} s")
    else:
        cols[2].metric("Duration", "—")

    if isinstance(pos, pd.DataFrame) and not pos.empty:
        cols[3].metric("GPS points", f"{len(pos):,}")
    else:
        cols[3].metric("GPS points", "—")


def _has_data(data: dict, key: str) -> bool:
    df = data.get(key) if isinstance(data, dict) else None
    return isinstance(df, pd.DataFrame) and not df.empty


def _render_time_series(data: dict):
    st.subheader("Flight parameters over time")

    options = []
    if _has_data(data, 'vfr_hud'):
        options.append('Throttle & Speed')
    if _has_data(data, 'attitude'):
        options.append('Attitude (Roll/Pitch/Yaw)')
    if _has_data(data, 'position'):
        options.append('Altitude')
    if _has_data(data, 'battery'):
        options.append('Battery')

    if not options:
        st.warning("No time-series data was extracted from this log.")
        return

    selected = st.multiselect("Parameters", options, default=options)

    chart_map = {
        'Throttle & Speed': ('vfr_hud', plot_throttle_speed),
        'Attitude (Roll/Pitch/Yaw)': ('attitude', plot_attitude),
        'Altitude': ('position', plot_altitude),
        'Battery': ('battery', plot_battery),
    }
    for label in selected:
        key, fn = chart_map[label]
        fig = fn(data.get(key))
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"{label}: no usable data.")


def _render_map(data: dict):
    st.subheader("Flight path")
    if not HAS_FOLIUM:
        st.error(
            "streamlit-folium is not installed. Install it with: "
            "`pip install streamlit-folium folium`"
        )
        return

    pos = data.get('position', pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
    if not isinstance(pos, pd.DataFrame) or pos.empty:
        st.warning("No GPS position data in this log.")
        return

    stats = compute_flight_stats(pos)
    if stats.get('points', 0) == 0:
        st.warning(
            "Position data was found but contains no valid GPS coordinates "
            "(all zero or NaN). Check the gps_raw table for fix_type."
        )
        return

    col_map, col_ctrl = st.columns([4, 1])
    with col_ctrl:
        tile_style = st.selectbox(
            "Map style",
            ['CartoDB dark_matter', 'CartoDB positron', 'OpenStreetMap'],
        )
        show_markers = st.checkbox("Start/end markers", value=True)
        n_points = max(stats.get('points', 1), 1)
        default_sample = max(1, n_points // 1500)
        sample_every = st.slider("Sample every N points", 1, 100, default_sample)
        st.caption(f"Rendering ~{n_points // sample_every:,} points")

    with col_map:
        flight_map = build_flight_map(
            pos, tile_style=tile_style,
            sample_every=sample_every, show_markers=show_markers,
        )
        if flight_map is None:
            st.warning("Could not build map from this data.")
        else:
            try:
                st_folium(
                    flight_map, height=520,
                    use_container_width=True, returned_objects=[],
                )
            except Exception as e:
                st.error(f"Map render failed: {e}")

    if stats:
        st.subheader("Flight statistics")
        cols = st.columns(5)
        cols[0].metric("Max altitude",
                       f"{stats['max_alt_m']:.1f} m" if 'max_alt_m' in stats else "—")
        cols[1].metric("Min altitude",
                       f"{stats['min_alt_m']:.1f} m" if 'min_alt_m' in stats else "—")
        cols[2].metric("Distance",
                       f"{stats['distance_m']:,.0f} m" if 'distance_m' in stats else "—")
        cols[3].metric("Duration",
                       f"{stats['duration_s']:.1f} s" if 'duration_s' in stats else "—")
        cols[4].metric("GPS points", f"{stats.get('points', 0):,}")


def _render_raw_data(data: dict):
    st.subheader("Parsed message tables")
    keys = [
        k for k, v in data.items()
        if not k.startswith('_') and isinstance(v, pd.DataFrame) and not v.empty
    ]
    if not keys:
        st.info("No parsed data tables available.")
        return

    selected = st.selectbox("Select message type", sorted(keys))
    df = data[selected]
    st.caption(f"{len(df):,} rows × {len(df.columns)} columns")
    try:
        st.dataframe(df.head(2000), use_container_width=True, height=420)
    except Exception as e:
        st.error(f"Could not render table: {e}")
        return

    try:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            csv,
            file_name=f"{selected}.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.warning(f"CSV export unavailable: {e}")


def _render_info(data: dict):
    meta = data.get('_meta', {}) if isinstance(data, dict) else {}
    st.subheader("Log metadata")
    info = {k: v for k, v in meta.items() if k != 'message_types'}
    st.json(info)

    msg_types = meta.get('message_types') or {}
    if msg_types:
        st.subheader("Message type frequencies")
        try:
            mt_df = (
                pd.DataFrame(
                    [{'type': k, 'count': v} for k, v in msg_types.items()]
                )
                .sort_values('count', ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(mt_df, use_container_width=True, height=360)
        except Exception as e:
            st.warning(f"Could not render message frequencies: {e}")


if __name__ == '__main__':
    main()
