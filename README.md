# UWL (Ultra‑local Wireless Locator) – Closed Network Container Tracking (Port)

This repository is a **prototype reference implementation** for a *closed, private* local positioning network for container yards.
It is designed to work **without public cloud** and to support **privacy-by-design** through encrypted “beacon” packets inspired by
the *Transport Encrypted Protocol (TEP)* approach (see `docs/` for a conceptual mapping).

> Note: RSSI-based positioning is **coarse** and strongly affected by multipath/reflections in container yards.
> For sub‑meter accuracy you generally need **Time‑of‑Flight / TDoA** (e.g., UWB / 802.15.4z) or **BLE Direction Finding (AoA)**.

## Inside this repository

- `uwl_gateway/` – gateway agent to run on Raspberry Pi nodes (anchors) that:
  - collects measurements (RSSI and/or ToA) from radios/sensors
  - wraps them into encrypted UWL packets
  - sends them to the central server over UDP
- `uwl_server/` – central server (FastAPI) that:
  - decrypts packets
  - stores measurements (SQLite)
  - computes tag positions (RSSI trilateration now; TDoA skeleton included)
  - exposes REST + WebSocket for dashboards
- `simulator/` – synthetic tag + anchor simulator for lab testing
- `docs/` – extended documentation and design notes

## Quick start (simulated)

### 1) Create a venv and install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Start the central server

```bash
python -m uwl_server.app --config configs/server.example.yaml
```

Server will listen on:
- UDP ingest: `0.0.0.0:5555`
- HTTP API: `0.0.0.0:8000`

### 3) Start a simulated yard with gateways and tags

```bash
python -m simulator.run --config configs/sim.example.yaml
```

### 4) Open the API

- `GET /health`
- `GET /tags`
- `GET /tags/{tag_id}/position`

## Security model (prototype)

- Packets are protected with **AES‑256‑GCM** (auth + confidentiality).
- Each gateway has an **ingest key** to talk to the server.
- Each tag may optionally use an **ephemeral ID** derived from a shared secret to reduce trackability.

This is not a full “blockchain” implementation; instead, it provides a practical **hash‑chaining** option (`chain_prev_hash`)
that can be enabled to make tampering/reordering detectable.

## Hardware mapping (suggested)

- **Anchors/Gateways**:
  - Raspberry Pi 4/5 + PoE HAT
  - BLE 5.1 AoA anchor *or* Wi‑Fi NIC for RSSI capture
  - Optionally UWB module for ToA/TDoA experiments (SPI/UART)
- **Tags**:
  - BLE beacon (for RSSI) or UWB tag (for ToF/TDoA)
  - battery (coin cell or Li‑SOCl2 for industrial longevity)

## License

MIT
