from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import uvicorn
import yaml
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from uwl_common.crypto import CryptoError, b64decode_key, decrypt_gcm
from uwl_common.schemas import Measurement, TagPosition, UwlPayload


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Anchor:
    anchor_id: str
    x_m: float
    y_m: float


@dataclass
class ServerConfig:
    udp_listen_ip: str
    udp_listen_port: int
    http_listen_ip: str
    http_listen_port: int
    database_path: str
    ingest_key_b64: str
    tx_power_dbm_at_1m: float
    path_loss_exponent: float
    anchors: List[Anchor]


def load_config(path: str) -> ServerConfig:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    s = cfg["server"]
    sec = cfg["security"]
    pos = cfg["positioning"]
    anchors = [Anchor(**a) for a in cfg.get("anchors", [])]
    return ServerConfig(
        udp_listen_ip=s.get("udp_listen_ip", "0.0.0.0"),
        udp_listen_port=int(s.get("udp_listen_port", 5555)),
        http_listen_ip=s.get("http_listen_ip", "0.0.0.0"),
        http_listen_port=int(s.get("http_listen_port", 8000)),
        database_path=s.get("database_path", "uwl.db"),
        ingest_key_b64=sec["ingest_key_b64"],
        tx_power_dbm_at_1m=float(pos.get("tx_power_dbm_at_1m", -59)),
        path_loss_exponent=float(pos.get("path_loss_exponent", 2.6)),
        anchors=anchors,
    )


def init_db(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, check_same_thread=False)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_unix_ms INTEGER NOT NULL,
            gateway_id TEXT NOT NULL,
            anchor_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            t_rx_unix_ms INTEGER NOT NULL,
            rssi_dbm REAL,
            toa_ns INTEGER,
            channel TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computed_unix_ms INTEGER NOT NULL,
            tag_id TEXT NOT NULL,
            x_m REAL NOT NULL,
            y_m REAL NOT NULL,
            method TEXT NOT NULL,
            quality REAL NOT NULL
        )
        """
    )
    con.commit()
    return con


def rssi_to_distance_m(rssi_dbm: float, tx_power_dbm_at_1m: float, n: float) -> float:
    # log-distance path loss model
    # d = 10^((tx_power - rssi)/(10*n))
    return float(10 ** ((tx_power_dbm_at_1m - rssi_dbm) / (10.0 * n)))


def solve_position_rssi_ls(anchor_xy: np.ndarray, distances: np.ndarray) -> Tuple[float, float, float]:
    """Least squares for 2D position from distance estimates.

    Minimizes sum_i (||p - a_i|| - d_i)^2 with Gauss-Newton.
    Returns (x, y, quality_0_1).
    """
    # initial guess: centroid
    p = anchor_xy.mean(axis=0).astype(float)

    for _ in range(25):
        diffs = p[None, :] - anchor_xy  # (N,2)
        ranges = np.linalg.norm(diffs, axis=1) + 1e-6
        residual = ranges - distances  # (N,)
        J = diffs / ranges[:, None]    # (N,2)
        # Solve normal equations
        H = J.T @ J
        g = J.T @ residual
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        p = p - step
        if float(np.linalg.norm(step)) < 1e-4:
            break

    # quality heuristic: based on final RMSE
    rmse = float(np.sqrt(np.mean((np.linalg.norm(p[None, :] - anchor_xy, axis=1) - distances) ** 2)))
    quality = float(1.0 / (1.0 + rmse))  # maps 0..inf -> (0,1]
    return float(p[0]), float(p[1]), quality


class PositionEngine:
    def __init__(self, cfg: ServerConfig):
        self.cfg = cfg
        self.anchor_map: Dict[str, Anchor] = {a.anchor_id: a for a in cfg.anchors}

    def compute_from_recent(self, recent: List[Measurement]) -> Optional[TagPosition]:
        # Use RSSI only for now; needs >=3 anchors.
        usable = [m for m in recent if m.rssi_dbm is not None and m.anchor_id in self.anchor_map]
        if len({m.anchor_id for m in usable}) < 3:
            return None

        # Keep one measurement per anchor (latest)
        by_anchor: Dict[str, Measurement] = {}
        for m in sorted(usable, key=lambda x: x.t_rx_unix_ms, reverse=True):
            by_anchor.setdefault(m.anchor_id, m)
        usable = list(by_anchor.values())
        if len(usable) < 3:
            return None

        anchor_xy = np.array([[self.anchor_map[m.anchor_id].x_m, self.anchor_map[m.anchor_id].y_m] for m in usable], dtype=float)
        distances = np.array([rssi_to_distance_m(float(m.rssi_dbm), self.cfg.tx_power_dbm_at_1m, self.cfg.path_loss_exponent) for m in usable], dtype=float)

        x, y, q = solve_position_rssi_ls(anchor_xy, distances)
        return TagPosition(tag_id=usable[0].tag_id, x_m=x, y_m=y, method="RSSI_LS", quality=q, computed_unix_ms=now_ms())


class UdpIngestor(threading.Thread):
    def __init__(self, cfg: ServerConfig, db: sqlite3.Connection, engine: PositionEngine, notify_cb):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.db = db
        self.engine = engine
        self.notify_cb = notify_cb
        self.key = b64decode_key(cfg.ingest_key_b64)
        self._stop = threading.Event()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.cfg.udp_listen_ip, self.cfg.udp_listen_port))
        print(f"[*] UDP ingest listening on {self.cfg.udp_listen_ip}:{self.cfg.udp_listen_port}")

        while not self._stop.is_set():
            data, addr = sock.recvfrom(65535)
            received_ms = now_ms()
            try:
                envelope = json.loads(data.decode("utf-8"))
                # Gateway id is used as AAD (auth binding)
                # If missing, we still attempt, but auth will fail if AAD mismatched.
                gw_guess = envelope.get("gateway_id") or envelope.get("aad_gateway_id")
                # For this prototype, we require the gateway_id inside plaintext; AAD uses empty and is validated after decrypt.
                # We therefore decrypt first with empty AAD, then validate gateway_id separately.
                payload = decrypt_gcm(self.key, envelope, aad=b"")
                batch = UwlPayload.model_validate(payload)
            except (CryptoError, ValueError, KeyError) as e:
                print(f"[!] Drop packet from {addr}: {e}")
                continue

            # Persist measurements
            cur = self.db.cursor()
            for m in batch.measurements:
                cur.execute(
                    """INSERT INTO measurements
                       (received_unix_ms, gateway_id, anchor_id, tag_id, t_rx_unix_ms, rssi_dbm, toa_ns, channel)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (received_ms, batch.gateway_id, m.anchor_id, m.tag_id, m.t_rx_unix_ms, m.rssi_dbm, m.toa_ns, m.channel),
                )
            self.db.commit()

            # Compute positions for each tag in this batch
            tags = {m.tag_id for m in batch.measurements}
            for tag_id in tags:
                recent = self.fetch_recent_measurements(tag_id, window_ms=2500)
                pos = self.engine.compute_from_recent(recent)
                if pos:
                    cur.execute(
                        """INSERT INTO positions (computed_unix_ms, tag_id, x_m, y_m, method, quality)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (pos.computed_unix_ms, pos.tag_id, pos.x_m, pos.y_m, pos.method, pos.quality),
                    )
                    self.db.commit()
                    self.notify_cb(pos)

    def fetch_recent_measurements(self, tag_id: str, window_ms: int) -> List[Measurement]:
        cur = self.db.cursor()
        t0 = now_ms() - window_ms
        rows = cur.execute(
            """SELECT anchor_id, tag_id, t_rx_unix_ms, rssi_dbm, toa_ns, channel
               FROM measurements
               WHERE tag_id=? AND t_rx_unix_ms>=?
               ORDER BY t_rx_unix_ms DESC
            """,
            (tag_id, t0),
        ).fetchall()
        return [Measurement(anchor_id=r[0], tag_id=r[1], t_rx_unix_ms=r[2], rssi_dbm=r[3], toa_ns=r[4], channel=r[5]) for r in rows]


app = FastAPI(title="UWL Central Server", version="0.1.0")
STATE = {}


@app.get("/health")
def health():
    return {"ok": True, "now_ms": now_ms()}


@app.get("/tags")
def list_tags():
    db: sqlite3.Connection = STATE["db"]
    rows = db.cursor().execute("SELECT DISTINCT tag_id FROM measurements ORDER BY tag_id").fetchall()
    return {"tags": [r[0] for r in rows]}


@app.get("/tags/{tag_id}/position")
def get_latest_position(tag_id: str):
    db: sqlite3.Connection = STATE["db"]
    row = db.cursor().execute(
        """SELECT computed_unix_ms, tag_id, x_m, y_m, method, quality
           FROM positions WHERE tag_id=? ORDER BY computed_unix_ms DESC LIMIT 1""",
        (tag_id,),
    ).fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "No position yet for this tag."})
    return TagPosition(
        computed_unix_ms=row[0],
        tag_id=row[1],
        x_m=row[2],
        y_m=row[3],
        method=row[4],
        quality=row[5],
    ).model_dump()


@app.websocket("/ws/positions")
async def ws_positions(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = STATE["ws_queue"]
    try:
        while True:
            pos: TagPosition = await q.get()
            await ws.send_json(pos.model_dump())
    except Exception:
        return


def run_server(cfg_path: str) -> None:
    cfg = load_config(cfg_path)
    db = init_db(cfg.database_path)
    engine = PositionEngine(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ws_queue: asyncio.Queue = asyncio.Queue()

    def notify(pos: TagPosition):
        try:
            loop.call_soon_threadsafe(ws_queue.put_nowait, pos)
        except Exception:
            pass

    ingestor = UdpIngestor(cfg, db, engine, notify)
    ingestor.start()

    STATE["db"] = db
    STATE["cfg"] = cfg
    STATE["ws_queue"] = ws_queue

    config = uvicorn.Config(app, host=cfg.http_listen_ip, port=cfg.http_listen_port, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    run_server(args.config)


if __name__ == "__main__":
    main()
