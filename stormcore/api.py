import requests
from datetime import datetime, timezone
from typing import Optional

BASE = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "STORMCORE-Desktop/1.0 (weather dashboard; contact: user@example.com)",
    "Accept": "application/geo+json"
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

class WeatherAPIError(Exception):
    pass

def _get(url, params=None):
    try:
        response = SESSION.get(url, params=params, timeout=18)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise WeatherAPIError(str(exc)) from exc

def geocode_city(query: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    data = requests.get(url, params={"name": query, "count": 8, "language": "en", "format": "json"}, timeout=15)
    data.raise_for_status()
    results = data.json().get("results", [])
    return [{
        "name": f'{x["name"]}, {x.get("admin1", x.get("country", ""))}',
        "latitude": x["latitude"], "longitude": x["longitude"],
        "country": x.get("country", ""), "timezone": x.get("timezone", "auto")
    } for x in results]

def point_metadata(lat, lon):
    return _get(f"{BASE}/points/{lat:.4f},{lon:.4f}")["properties"]

def forecast(lat, lon, hourly=False):
    meta = point_metadata(lat, lon)
    key = "forecastHourly" if hourly else "forecast"
    return _get(meta[key])["properties"]

def alerts(lat, lon):
    data = _get(f"{BASE}/alerts/active", {"point": f"{lat:.4f},{lon:.4f}"})
    return data.get("features", [])

def stations(lat, lon):
    data = _get(f"{BASE}/points/{lat:.4f},{lon:.4f}/stations")
    return data.get("features", [])

def observations(station_id):
    data = _get(f"{BASE}/stations/{station_id}/observations/latest")
    return data.get("properties", {})

def radar_metadata():
    # RainViewer publishes its current radar tile frames as a public JSON feed.
    r = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=15)
    r.raise_for_status()
    return r.json()

def celsius_to_f(value):
    return round(value * 9 / 5 + 32) if value is not None else None

def format_temp(value, unit="F"):
    if value is None:
        return "—"
    return f"{round(value)}°{unit}"

def parse_time(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%a %I:%M %p")
    except Exception:
        return value
