# Extended Design Notes (UWL closed port network)

## Problem
Track the **exact yard position** of shipping containers in a port using a **closed/private local network**, with:
- low-power tags on each container
- fixed anchors/gateways around the yard
- a central control server for visualization and integration (e.g., WMS/TOS)

## Why RSSI alone is not enough
Container yards create **severe multipath** and shadowing. RSSI fluctuates even when the tag is stationary.
RSSI can still be useful for:
- coarse position / zone detection
- alarm thresholds ("wrong zone", "gate crossing")
- fallback mode when precise ranging is unavailable

For high precision, use:
- **UWB ToF/TDoA** (e.g., IEEE 802.15.4z)
- **BLE 5.1 Direction Finding (AoA/AoD)**

## Architecture
### Tag (container)
- emits periodic encrypted beacons
- battery powered
- optional motion sensor to reduce duty cycle while static

### Anchor/Gateway (fixed, PoE)
- receives beacons; measures:
  - RSSI (always)
  - optionally ToA (if supported by radio)
- forwards encrypted measurement batches to central server via LAN

### Central Server
- decrypts and validates envelopes
- stores measurements + computed positions
- computes positions:
  - RSSI least-squares now (prototype)
  - TDoA least-squares (requires anchor time sync)
- exposes APIs and dashboard integration

## Security / TEP-inspired mapping
The referenced TEP patent describes concepts such as:
- encrypted packet transport at higher layers (OSI)
- blockchain/hashed packet structures
- virtualization/dematerialization of BTS into "DBTS"

UWL maps those ideas pragmatically as:
- **end-to-end authenticated encryption** for measurement transport
- optional **hash chaining** for tamper/reorder detection
- **virtualized control plane** in software (central server) with many cheap edge nodes

This prototype intentionally stays implementable on COTS hardware.
