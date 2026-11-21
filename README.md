# STORMCORE — Windows Weather Command Center

STORMCORE is a Python + PySide6 desktop weather dashboard using live public weather feeds.

## Features
- Active National Weather Service alerts for the selected point, including tornado, severe thunderstorm, winter, and flood alerts when issued by NWS.
- NWS forecast and hourly forecast.
- Live US radar overlay using RainViewer radar tiles over OpenStreetMap.
- City search and saved locations.
- Nearby NWS observation stations and latest reported observations.
- Broadcast studio that exports a 1600×900 PNG forecast graphic.
- Automatic refresh of weather and alerts every 5 minutes; radar refreshes every 10 minutes.
- Windows system-tray icon with refresh and quit actions.

## Data sources and notes
- NOAA / National Weather Service API: https://api.weather.gov
- Open-Meteo geocoding API: https://geocoding-api.open-meteo.com
- RainViewer radar feed: https://api.rainviewer.com/public/weather-maps.json
- OpenStreetMap base map: https://www.openstreetmap.org

The NWS API is the authoritative source for official US watches and warnings. STORMCORE displays active alerts returned for the selected map point; it does not independently issue, interpret, or guarantee warnings. Always follow official NWS alerts and local emergency instructions. Radar tiles can have provider coverage or latency limitations.

The NWS requests include a generic User-Agent. For a public deployment, replace the contact placeholder in `stormcore/api.py` with a real project contact address, in line with NWS API guidance.

## Windows installation

1. Install **Python 3.11 or newer** from https://www.python.org/downloads/windows/ and enable **Add Python to PATH**.
2. Extract the STORMCORE ZIP to a folder such as `C:\\STORMCORE`.
3. Open Command Prompt or PowerShell in that folder.
4. Create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   ```

   If PowerShell blocks activation, run `\\.venv\\Scripts\\activate.bat` from Command Prompt instead.
5. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
6. Launch:

   ```powershell
   python main.py
   ```

## Optional: build a standalone EXE

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name STORMCORE --collect-all PySide6 --collect-all shiboken6 --collect-all PySide6.QtWebEngineCore main.py
```

The executable will be placed in `dist\\STORMCORE\\` (or `dist\\STORMCORE.exe`, depending on the PyInstaller version). Test the packaged build on the target Windows machine.

## Troubleshooting
- **Radar blank:** confirm internet access and that the RainViewer feed and Leaflet CDN are reachable. The map base layer and radar overlay are remote resources.
- **NWS request errors:** retry later. NWS services may rate-limit or temporarily return errors.
- **No alerts:** this means the NWS point query returned no active alerts for the selected coordinates at refresh time.
- **Station observations unavailable:** not every station reports every sensor field; missing values appear as em dashes.
- **Notifications:** this release uses the Windows system-tray integration; popup notifications depend on Windows notification settings. The app refreshes alerts automatically, but does not yet provide a separate per-alert notification history.

## Project layout

```text
STORMCORE/
├── main.py
├── requirements.txt
├── README.md
└── stormcore/
    ├── __init__.py
    ├── api.py
    ├── graphics.py
    ├── radar.html
    └── ui.py
```
