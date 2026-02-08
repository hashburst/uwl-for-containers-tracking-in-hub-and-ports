# Flask Dashboard (Simple CRS) for Yard Visualization

This document describes a minimal dashboard to visualize container/tag positions on a planar yard map.

- Backend: Flask
- Frontend map: Leaflet
- Coordinate system: **Simple CRS** (meters, not lat/long)

This is useful when your localization outputs `(x,y)` in meters relative to a yard origin.

## Directory layout

```
extras/dashboard_flask/
  app.py
  kalman.py
  templates/
    index.html
  requirements-dashboard.txt
```

## Install and run

```bash
cd extras/dashboard_flask
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dashboard.txt
python app.py
```

Open:

- `http://127.0.0.1:5000`

## How it works

- `app.py` queries the central server API (or a local generator) for the latest `(x,y)` position.
- The dashboard renders a 2D yard view using `L.CRS.Simple` so that map units match meters.

## Integrating with the UWL server

In `app.py`, set the server URL:

- `UWL_SERVER_BASE = "http://127.0.0.1:8000"`

Then fetch a position endpoint like:

- `/tags/{tag_id}/position`

## Tips for production

- Add authentication (even in LAN).
- Persist tracks and add replay mode.
- Show measurement quality (residual error, anchor count, RSSI/UWB health).
- Overlay a real yard blueprint image as the Leaflet base layer for better operator UX.
