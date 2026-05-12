# Drone Data Analytics

A Streamlit tool for parsing and visualizing drone flight logs. Built for ArduPilot, PX4, and generic MAVLink workflows.

## Features

- **Smart file selector** — validates extension, size, and emptiness before parsing. Tells you exactly why a file was rejected.
- **Multi-format parser**
  - `.tlog` — MAVLink telemetry logs (ground-station recordings)
  - `.bin` — ArduPilot DataFlash binary logs (onboard SD)
  - `.log` — ArduPilot text logs
  - `.tlv` — Generic Type-Length-Value byte streams
- **Interactive Plotly time-series** — throttle, airspeed, groundspeed, attitude, altitude, battery
- **Folium flight map** — GPS path colored by altitude, start/end markers, three map styles
- **Raw data inspector** with CSV export for every parsed message type
- **Per-tab error boundaries** — a broken chart never takes down the whole app
- **Memory caps** on huge files (2M messages, 500K TLV records) so the app stays responsive

---

## Windows setup — full walkthrough

### 1. Install Python 3.10 or newer

Download from <https://www.python.org/downloads/windows/>.

When the installer runs, **check the box "Add python.exe to PATH"** before clicking Install. This is the single most common cause of setup failures.

Verify after install (open a new PowerShell or Command Prompt):

```powershell
python --version
```

You should see `Python 3.10.x` or higher.

### 2. Get the project files

Either clone the repo or download the seven files (`app.py`, `parsers.py`, `visualizations.py`, `utils.py`, `requirements.txt`, `run.bat`, `README.md`) into one folder, for example `C:\Users\you\drone_analytics\`.

### 3. Run it

Double-click **`run.bat`**. On the first run it will:

1. Check your Python version
2. Create a virtual environment in `.venv\`
3. Install all dependencies from `requirements.txt`
4. Launch Streamlit and open <http://localhost:8501> in your browser

Subsequent runs skip the install step and start in a few seconds.

### Manual setup (if you prefer)

```powershell
cd C:\Users\you\drone_analytics
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

To stop the app, press **Ctrl+C** in the terminal window.

---

## Project layout

```
drone_analytics/
├── app.py              # Streamlit UI + tabs + error boundaries
├── parsers.py          # MAVLink / ArduPilot / TLV parsing
├── visualizations.py   # Plotly charts + Folium map helpers
├── utils.py            # File validation, formatters
├── requirements.txt    # Pinned dependency ranges
├── run.bat             # Windows launcher
├── .gitignore
└── README.md
```

## Common-schema dict produced by all parsers

The parsers normalize every input format into the same dict-of-DataFrames so the UI layer doesn't care which format you uploaded:

| Key         | Columns                                                              |
| ----------- | -------------------------------------------------------------------- |
| `position`  | `timestamp, lat, lon, alt, relative_alt, vx, vy, vz, heading`       |
| `attitude`  | `timestamp, roll, pitch, yaw` (radians)                              |
| `vfr_hud`   | `timestamp, throttle, airspeed, groundspeed, alt, climb`             |
| `battery`   | `timestamp, voltage, current, remaining`                             |
| `gps_raw`   | `timestamp, fix_type, satellites, lat, lon, alt`                     |
| `heartbeat` | `timestamp, base_mode, custom_mode, system_status`                   |
| `_meta`     | `format, total_messages, message_types, errors, capped`              |

Every frame also gets `elapsed` (seconds from log start) and `datetime` when timestamps are present.

ArduPilot DataFlash logs additionally expose the raw message tables (`GPS`, `ATT`, `CTUN`, `BAT`, `RCIN`, `RCOU`, etc.) under their native names in the Raw Data tab.

---

## Troubleshooting

**"python is not recognized as an internal or external command"**
Python isn't on PATH. Reinstall and check the "Add Python to PATH" box, or add it manually via System Properties → Environment Variables.

**`pip install pymavlink` fails to build on Windows**
Install Microsoft C++ Build Tools from <https://visualstudio.microsoft.com/visual-cpp-build-tools/>, or force a prebuilt wheel:
```powershell
pip install --only-binary=:all: pymavlink
```

**Browser doesn't open automatically**
Visit <http://localhost:8501> manually. If that's blocked, check your firewall rules — Streamlit binds to localhost only by default.

**"streamlit-folium is not installed" appears in the Flight Map tab**
Reinstall with `pip install streamlit-folium folium` inside the activated venv.

**Empty Flight Map but the log has GPS**
Some logs have all-zero coordinates when no fix was acquired. Open the Raw Data tab and check the `gps_raw` table — `fix_type` values of 0 or 1 mean no usable position.

**Large `.bin` file is very slow**
The parser is single-threaded by design (pymavlink limitation). For logs >100 MB, split with MissionPlanner's log extractor first, or rely on the built-in 2M-message cap (the app will warn you it kicked in).

**Port 8501 already in use**
Stop the other Streamlit process or launch on a different port:
```powershell
streamlit run app.py --server.port 8502
```

**Permission denied on temp file (rare, antivirus-related)**
Add an exclusion for your `.venv\` folder in Windows Security → Virus & threat protection → Exclusions.

---

## Roadmap

- **Phase 2 — Video stream sync.** Load a companion MP4/MKV, sync to log timestamps, overlay HUD on video frames.
- **Phase 3 — Anomaly detection.** Flag vibration spikes, EKF errors, GPS glitches, sudden current draws.
- **Phase 4 — ULog (`.ulg`) support** for pure PX4 stacks (via `pyulog`).
- **Phase 5 — Multi-log comparison.** Overlay two flights side-by-side to compare tuning changes.

## Extending parsers

To plug in a new format, add a method to `DroneLogParser` in `parsers.py`, route to it from `parse()`, and populate `self.data` with the common schema above. The UI auto-detects which tables are present and renders accordingly.

```python
elif self.ext == '.mylog':
    self._parse_my_format()
```
