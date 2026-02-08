from __future__ import annotations

import argparse
import json
import math
import random
import socket
import time
from dataclasses import dataclass
from typing import Dict, List

import yaml

from uwl_common.crypto import b64decode_key, encrypt_gcm
from uwl_common.schemas import Measurement, UwlPayload


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Anchor:
    anchor_id: str
    x_m: float
    y_m: float


@dataclass
class Tag:
    tag_id: str
    x_m: float
    y_m: float


def load_cfg(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rssi_from_distance(d_m: float, tx_power_dbm_at_1m: float, n: float, noise_std: float) -> float:
    d_m = max(d_m, 0.3)
    mean = tx_power_dbm_at_1m - 10.0 * n * math.log10(d_m)
    return random.gauss(mean, noise_std)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    server_ip = cfg["simulation"]["server_ip"]
    server_port = int(cfg["simulation"]["server_port"])
    tick_hz = float(cfg["simulation"].get("tick_hz", 1.0))

    anchors = [Anchor(**a) for a in cfg["yard"]["anchors"]]
    tags = [Tag(**t) for t in cfg["yard"]["tags"]]

    tx_power = float(cfg["radio_model"]["tx_power_dbm_at_1m"])
    n = float(cfg["radio_model"]["path_loss_exponent"])
    noise = float(cfg["radio_model"]["rssi_noise_std_db"])

    key = b64decode_key(cfg["security"]["ingest_key_b64"])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seq = 0
    prev_hash = None
    period = 1.0 / max(tick_hz, 0.1)

    print(f"[*] Simulator -> {server_ip}:{server_port} tick={tick_hz}Hz")
    while True:
        seq += 1
        ms = []
        for tag in tags:
            for a in anchors:
                d = math.hypot(tag.x_m - a.x_m, tag.y_m - a.y_m)
                rssi = rssi_from_distance(d, tx_power, n, noise)
                ms.append(
                    Measurement(
                        anchor_id=a.anchor_id,
                        tag_id=tag.tag_id,
                        t_rx_unix_ms=now_ms(),
                        rssi_dbm=rssi,
                        toa_ns=None,
                        channel="SIM-RSSI",
                    )
                )

        payload = UwlPayload(
            gateway_id="SIM-GW",
            seq=seq,
            sent_unix_ms=now_ms(),
            measurements=ms,
        ).model_dump()

        envelope = encrypt_gcm(key, payload, aad=b"", prev_hash_hex=prev_hash)
        prev_hash = envelope["sha256_hex"]

        sock.sendto(json.dumps(envelope).encode("utf-8"), (server_ip, server_port))
        time.sleep(period)


if __name__ == "__main__":
    main()
