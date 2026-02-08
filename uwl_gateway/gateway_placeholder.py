from __future__ import annotations

import argparse
import json
import socket
import time
from dataclasses import dataclass
from typing import List, Optional

import yaml

from uwl_common.crypto import b64decode_key, encrypt_gcm
from uwl_common.schemas import Measurement, UwlPayload


@dataclass
class GatewayConfig:
    gateway_id: str
    server_ip: str
    server_port: int
    ingest_key_b64: str
    tick_hz: float = 1.0
    # For real deployments: configure radio backends (BLE scan, UWB, etc.)
    mode: str = "simulated"
    anchor_id: str = "A1"


def now_ms() -> int:
    return int(time.time() * 1000)


def load_config(path: str) -> GatewayConfig:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    g = cfg.get("gateway", {})
    s = cfg.get("server", {})
    sec = cfg.get("security", {})
    return GatewayConfig(
        gateway_id=g.get("gateway_id", "GW-UNKNOWN"),
        server_ip=s["ip"],
        server_port=int(s.get("port", 5555)),
        ingest_key_b64=sec["ingest_key_b64"],
        tick_hz=float(g.get("tick_hz", 1.0)),
        mode=g.get("mode", "simulated"),
        anchor_id=g.get("anchor_id", "A1"),
    )


def simulated_measurements(anchor_id: str) -> List[Measurement]:
    # This is a placeholder: in real gateway you would read BLE/UWB measurements and produce one Measurement per observed tag. Here we emit nothing; simulator normally sends directly to server.
    return [
        Measurement(
            anchor_id=anchor_id,
            tag_id="T001",
            t_rx_unix_ms=now_ms(),
            rssi_dbm=-70.0,
            toa_ns=None,
            channel="SIM",
        )
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="YAML config for this gateway")
    args = ap.parse_args()

    cfg = load_config(args.config)
    key = b64decode_key(cfg.ingest_key_b64)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0
    prev_hash = None

    period = 1.0 / max(cfg.tick_hz, 0.1)
    print(f"[*] Gateway {cfg.gateway_id} -> {cfg.server_ip}:{cfg.server_port} mode={cfg.mode}")

    while True:
        seq += 1
        measurements = simulated_measurements(cfg.anchor_id)

        payload = UwlPayload(
            gateway_id=cfg.gateway_id,
            seq=seq,
            sent_unix_ms=now_ms(),
            measurements=measurements,
        ).model_dump()

        envelope = encrypt_gcm(key, payload, aad=cfg.gateway_id.encode("utf-8"), prev_hash_hex=prev_hash)
        prev_hash = envelope["sha256_hex"]

        sock.sendto(json.dumps(envelope).encode("utf-8"), (cfg.server_ip, cfg.server_port))
        time.sleep(period)


if __name__ == "__main__":
    main()
