"""Visualization helpers for drone analytics."""
from __future__ import annotations

from typing import Optional

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Consistent color palette
COLORS = {
    'primary': '#ff6b6b',
    'secondary': '#4ecdc4',
    'tertiary': '#95e1d3',
    'accent': '#ffd93d',
    'good': '#6bcf7f',
    'bg': '#0e1117',
    'grid': '#2a2f3a',
}


def _empty(df) -> bool:
    """Defensive emptiness check that handles None and non-DataFrame inputs."""
    if df is None:
        return True
    if not isinstance(df, pd.DataFrame):
        return True
    return df.empty


def _x_axis(df: pd.DataFrame):
    """Pick the best x-axis column from a frame."""
    if 'elapsed' in df.columns and df['elapsed'].notna().any():
        return df['elapsed'], 'Time elapsed (s)'
    if 'datetime' in df.columns and df['datetime'].notna().any():
        return df['datetime'], 'Time'
    return df.index, 'Sample #'


def _base_layout(title: str, xlabel: str) -> dict:
    """Common dark-theme layout for all charts."""
    return dict(
        title=dict(text=title, font=dict(size=13, color='#fafafa'),
                   x=0.01, xanchor='left'),
        height=320,
        paper_bgcolor=COLORS['bg'],
        plot_bgcolor=COLORS['bg'],
        font=dict(color='#fafafa', size=12),
        margin=dict(l=60, r=60, t=45, b=45),
        hovermode='x unified',
        xaxis=dict(gridcolor=COLORS['grid'], title=xlabel, zeroline=False),
        yaxis=dict(gridcolor=COLORS['grid'], zeroline=False),
        legend=dict(orientation='h', y=-0.22),
    )


def plot_throttle_speed(vfr_hud: pd.DataFrame) -> Optional[go.Figure]:
    if _empty(vfr_hud):
        return None
    try:
        x, xlabel = _x_axis(vfr_hud)
        fig = go.Figure()
        added = False
        if 'throttle' in vfr_hud.columns and vfr_hud['throttle'].notna().any():
            fig.add_trace(go.Scatter(
                x=x, y=vfr_hud['throttle'], name='Throttle (%)',
                line=dict(color=COLORS['primary'], width=1.75),
            ))
            added = True
        for col, color, label in [
            ('airspeed', COLORS['secondary'], 'Airspeed (m/s)'),
            ('groundspeed', COLORS['tertiary'], 'Groundspeed (m/s)'),
        ]:
            if col in vfr_hud.columns and vfr_hud[col].notna().any():
                fig.add_trace(go.Scatter(
                    x=x, y=vfr_hud[col], name=label,
                    line=dict(color=color, width=1.75), yaxis='y2',
                ))
                added = True
        if not added:
            return None
        layout = _base_layout('Throttle & Speed', xlabel)
        layout['yaxis']['title'] = 'Throttle (%)'
        layout['yaxis2'] = dict(
            title='Speed (m/s)', side='right', overlaying='y',
            gridcolor=COLORS['grid'], zeroline=False,
        )
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def plot_attitude(attitude: pd.DataFrame) -> Optional[go.Figure]:
    if _empty(attitude):
        return None
    try:
        x, xlabel = _x_axis(attitude)
        fig = go.Figure()
        added = False
        for col, color in [
            ('roll', COLORS['primary']),
            ('pitch', COLORS['secondary']),
            ('yaw', COLORS['tertiary']),
        ]:
            if col not in attitude.columns:
                continue
            vals = pd.to_numeric(attitude[col], errors='coerce')
            if not vals.notna().any():
                continue
            # If values look like radians (abs max < 2π), convert to degrees
            max_abs = vals.abs().max()
            if pd.notna(max_abs) and max_abs < 7:
                vals = np.degrees(vals)
            fig.add_trace(go.Scatter(
                x=x, y=vals, name=col.title(),
                line=dict(color=color, width=1.75),
            ))
            added = True
        if not added:
            return None
        layout = _base_layout('Attitude (degrees)', xlabel)
        layout['yaxis']['title'] = 'Degrees'
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def plot_altitude(position: pd.DataFrame) -> Optional[go.Figure]:
    if _empty(position):
        return None
    try:
        x, xlabel = _x_axis(position)
        fig = go.Figure()
        added = False
        if 'alt' in position.columns and position['alt'].notna().any():
            fig.add_trace(go.Scatter(
                x=x, y=position['alt'], name='Altitude MSL (m)',
                fill='tozeroy',
                line=dict(color=COLORS['accent'], width=1.75),
                fillcolor='rgba(255, 217, 61, 0.12)',
            ))
            added = True
        if 'relative_alt' in position.columns and position['relative_alt'].notna().any():
            fig.add_trace(go.Scatter(
                x=x, y=position['relative_alt'], name='Relative Alt (m)',
                line=dict(color=COLORS['good'], width=1.75),
            ))
            added = True
        if not added:
            return None
        layout = _base_layout('Altitude', xlabel)
        layout['yaxis']['title'] = 'Meters'
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def plot_battery(battery: pd.DataFrame) -> Optional[go.Figure]:
    if _empty(battery):
        return None
    try:
        x, xlabel = _x_axis(battery)
        fig = go.Figure()
        added = False
        if 'voltage' in battery.columns and battery['voltage'].notna().any():
            fig.add_trace(go.Scatter(
                x=x, y=battery['voltage'], name='Voltage (V)',
                line=dict(color=COLORS['primary'], width=1.75),
            ))
            added = True
        if 'current' in battery.columns and battery['current'].notna().any():
            fig.add_trace(go.Scatter(
                x=x, y=battery['current'], name='Current (A)',
                line=dict(color=COLORS['secondary'], width=1.75), yaxis='y2',
            ))
            added = True
        if not added:
            return None
        layout = _base_layout('Battery', xlabel)
        layout['yaxis']['title'] = 'Voltage (V)'
        layout['yaxis2'] = dict(
            title='Current (A)', side='right', overlaying='y',
            gridcolor=COLORS['grid'], zeroline=False,
        )
        fig.update_layout(**layout)
        return fig
    except Exception:
        return None


def _clean_position(position: pd.DataFrame) -> pd.DataFrame:
    """Filter to rows with valid lat/lon."""
    if _empty(position) or 'lat' not in position.columns or 'lon' not in position.columns:
        return pd.DataFrame()
    df = position.copy()
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df = df.dropna(subset=['lat', 'lon'])
    df = df[df['lat'].between(-90, 90) & df['lon'].between(-180, 180)]
    df = df[(df['lat'] != 0) | (df['lon'] != 0)]
    return df


def build_flight_map(
    position: pd.DataFrame,
    tile_style: str = 'CartoDB dark_matter',
    sample_every: int = 1,
    show_markers: bool = True,
) -> Optional[folium.Map]:
    """Build a folium map showing the flight path."""
    pos = _clean_position(position)
    if pos.empty:
        return None

    try:
        sample_every = max(1, int(sample_every))
    except (TypeError, ValueError):
        sample_every = 1

    pos = pos.iloc[::sample_every]
    if pos.empty:
        return None

    try:
        center = [float(pos['lat'].mean()), float(pos['lon'].mean())]
        m = folium.Map(
            location=center, zoom_start=16,
            tiles=tile_style, control_scale=True,
        )

        coords = pos[['lat', 'lon']].values.tolist()
        if len(coords) < 2:
            # Single point — drop a marker and exit
            folium.CircleMarker(
                coords[0], radius=6, color=COLORS['primary'],
                fill=True, popup='Single GPS point',
            ).add_to(m)
            return m

        # Altitude-graded path coloring (blue=low → red=high)
        if 'alt' in pos.columns and pos['alt'].notna().any():
            alts = pos['alt'].values.astype(float)
            valid_alts = alts[~np.isnan(alts)]
            if len(valid_alts) > 0:
                amin, amax = float(np.min(valid_alts)), float(np.max(valid_alts))
                arange = max(amax - amin, 0.001)
                for i in range(len(coords) - 1):
                    a = alts[i]
                    if np.isnan(a):
                        color = COLORS['primary']
                    else:
                        t = (a - amin) / arange
                        r = int(255 * t)
                        b = int(255 * (1 - t))
                        color = f'#{r:02x}40{b:02x}'
                    folium.PolyLine(
                        [coords[i], coords[i + 1]],
                        color=color, weight=2.5, opacity=0.9,
                    ).add_to(m)
            else:
                folium.PolyLine(coords, color=COLORS['primary'],
                                weight=2.5, opacity=0.9).add_to(m)
        else:
            folium.PolyLine(coords, color=COLORS['primary'],
                            weight=2.5, opacity=0.9).add_to(m)

        if show_markers:
            for coord, color, label in [
                (coords[0], COLORS['good'], 'Start'),
                (coords[-1], COLORS['primary'], 'End'),
            ]:
                folium.CircleMarker(
                    coord, radius=6, color=color, fill=True,
                    fill_color=color, fill_opacity=1.0, weight=2,
                    popup=label,
                ).add_to(m)

        # Fit bounds with a small padding
        sw = [pos['lat'].min(), pos['lon'].min()]
        ne = [pos['lat'].max(), pos['lon'].max()]
        if sw != ne:
            m.fit_bounds([sw, ne], padding=(20, 20))
        return m
    except Exception:
        return None


def compute_flight_stats(position: pd.DataFrame) -> dict:
    """Compute summary stats from a position dataframe. Never raises."""
    stats: dict = {}
    pos = _clean_position(position)
    if pos.empty:
        return stats

    try:
        if 'alt' in pos.columns and pos['alt'].notna().any():
            stats['max_alt_m'] = float(pos['alt'].max())
            stats['min_alt_m'] = float(pos['alt'].min())

        if len(pos) > 1:
            lats = np.radians(pos['lat'].values.astype(float))
            lons = np.radians(pos['lon'].values.astype(float))
            dlat = np.diff(lats)
            dlon = np.diff(lons)
            a = (np.sin(dlat / 2) ** 2
                 + np.cos(lats[:-1]) * np.cos(lats[1:]) * np.sin(dlon / 2) ** 2)
            c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            dist_m = float(np.nansum(6371000 * c))
            stats['distance_m'] = dist_m

        stats['points'] = int(len(pos))

        if 'elapsed' in pos.columns and pos['elapsed'].notna().any():
            stats['duration_s'] = float(pos['elapsed'].max())
    except Exception:
        # Stats are best-effort; partial results are still useful
        pass

    return stats
