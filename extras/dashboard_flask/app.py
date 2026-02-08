from __future__ import annotations

import os
from typing import Dict

import requests
from flask import Flask, jsonify, render_template

from kalman import Kalman2D

APP_HOST = os.environ.get("DASH_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("DASH_PORT", "5000"))

UWL_SERVER_BASE = os.environ.get("UWL_SERVER_BASE", "http://127.0.0.1:8000")
DEFAULT_TAG_ID = os.environ.get("TAG_ID", "T001")

# One Kalman filter per tag
filters: Dict[str, Kalman2D] = {}

app = Flask(__name__)


def get_filter(tag_id: str) -> Kalman2D:
    if tag_id not in filters:
        filters[tag_id] = Kalman2D(dt=1.0, process_noise=0.1, measurement_noise=5.0)
    return filters[tag_id]


@app.get("/")
def index():
    return render_template("index.html", tag_id=DEFAULT_TAG_ID, server_base=UWL_SERVER_BASE)


@app.get("/api/position/<tag_id>")
def api_position(tag_id: str):
    """Proxy the latest position from uwl_server and apply Kalman smoothing."""

    # uwl_server endpoint created by this repository
    url = f"{UWL_SERVER_BASE}/tags/{tag_id}/position"
    r = requests.get(url, timeout=2)
    if r.status_code != 200:
        return jsonify({"error": f"uwl_server returned {r.status_code}"}), 502

    payload = r.json()
    # expected: {tag_id, x_m, y_m, updated_unix_ms, source}
    x = float(payload.get("x_m", 0.0))
    y = float(payload.get("y_m", 0.0))

    kf = get_filter(tag_id)
    kf.predict()
    kf.update((x, y))
    fx, fy = kf.pos

    return jsonify(
        {
            "tag_id": tag_id,
            "raw_x": x,
            "raw_y": y,
            "x": fx,
            "y": fy,
            "updated_unix_ms": payload.get("updated_unix_ms"),
            "source": payload.get("source"),
        }
    )


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=True)
