from __future__ import annotations

import argparse
import json
import socket
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

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
    # supported: simulated | uwb_serial
    mode: str = "simulated"
    anchor_id: str = "A1"

    # UWB-over-serial settings (e.g., Qorvo DWM3xxx dev board / anchor firmware)
    uwb_serial_device: str = "/dev/ttyACM0"
    uwb_serial_baud: int = 115200
    # If your UWB firmware prints JSON lines, configure the keys here.
    # Expected JSON per line (example):
    # {"tag_id":"T001","rssi_dbm":-74.2,"toa_ns":1700000000123456789}
    uwb_json_tag_key: str = "tag_id"
    uwb_json_rssi_key: str = "rssi_dbm"
    uwb_json_toa_key: str = "toa_ns"


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
        uwb_serial_device=g.get("uwb_serial_device", "/dev/ttyACM0"),
        uwb_serial_baud=int(g.get("uwb_serial_baud", 115200)),
        uwb_json_tag_key=g.get("uwb_json_tag_key", "tag_id"),
        uwb_json_rssi_key=g.get("uwb_json_rssi_key", "rssi_dbm"),
        uwb_json_toa_key=g.get("uwb_json_toa_key", "toa_ns"),
    )


def simulated_measurements(anchor_id: str) -> List[Measurement]:
    """Simulation-only measurements.

    Kept as a safe fallback when the radio backend is not available.
    """
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


def uwb_serial_measurements(
    *,
    anchor_id: str,
    serial_dev: str,
    baud: int,
    json_keys: Dict[str, str],
    max_lines: int = 25,
    timeout_s: float = 0.15,
) -> List[Measurement]:
    """Read UWB measurements from a serial-connected UWB anchor module.

    Why serial?
      Many UWB modules/dev boards (including common DWM3xxx-based prototypes)
      expose ranging or receive events over UART/USB CDC.

    Expected format:
      One JSON object per line, at least containing tag id and ToA or TDoA-related timestamp.
      Example line:
        {"tag_id":"T001","rssi_dbm":-74.2,"toa_ns":1700000000123456789}

    Notes on UWB and anti-jamming:
      UWB operates using very short pulses over a wide bandwidth (e.g., ~6.5–9 GHz in some
      deployments). A wide occupied bandwidth increases the effort required for narrowband
      interferers to deny service across the whole signal, but it does NOT make a system
      "unjammable". This gateway function focuses on collecting ToA/quality metrics; resilience
      also depends on PHY settings, detection thresholds, and deployment density.
    """
    try:
        import serial  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "pyserial is required for mode=uwb_serial. Install: pip install pyserial"
        ) from e

    tag_k = json_keys["tag"]
    rssi_k = json_keys["rssi"]
    toa_k = json_keys["toa"]

    out: List[Measurement] = []
    with serial.Serial(serial_dev, baudrate=baud, timeout=timeout_s) as ser:
        # Drain a small burst of lines; each line may contain one observation.
        for _ in range(max_lines):
            raw = ser.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Accept both pure JSON lines and lines prefixed with text.
            try:
                start = line.find("{")
                if start > 0:
                    line = line[start:]
                obj = json.loads(line)
            except Exception:
                continue

            tag_id = obj.get(tag_k)
            if not tag_id:
                continue

            rssi = obj.get(rssi_k)
            toa = obj.get(toa_k)

            # Normalize types
            rssi_dbm: Optional[float] = None
            if rssi is not None:
                try:
                    rssi_dbm = float(rssi)
                except Exception:
                    rssi_dbm = None

            toa_ns: Optional[int] = None
            if toa is not None:
                try:
                    toa_ns = int(toa)
                except Exception:
                    toa_ns = None

            out.append(
                Measurement(
                    anchor_id=anchor_id,
                    tag_id=str(tag_id),
                    t_rx_unix_ms=now_ms(),
                    rssi_dbm=rssi_dbm,
                    toa_ns=toa_ns,
                    channel="UWB-SERIAL",
                )
            )

    return out


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
        if cfg.mode == "uwb_serial":
            try:
                measurements = uwb_serial_measurements(
                    anchor_id=cfg.anchor_id,
                    serial_dev=cfg.uwb_serial_device,
                    baud=cfg.uwb_serial_baud,
                    json_keys={
                        "tag": cfg.uwb_json_tag_key,
                        "rssi": cfg.uwb_json_rssi_key,
                        "toa": cfg.uwb_json_toa_key,
                    },
                )
            except Exception as e:
                # Fallback keeps the gateway alive while you debug serial/UWB firmware.
                print(f"[!] UWB serial backend failed ({e}); falling back to simulated.")
                measurements = simulated_measurements(cfg.anchor_id)
        else:
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
