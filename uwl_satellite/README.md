# UWL Global Tracking: Satellite Integration Core

## Hardware Design Parameters (Prototyping Roadmap)

Since the executive project parameters are still being defined, this software core is built to support the following hardware assumptions and integration requirements:

### 1. Iridium Modem (Backup Connectivity)
* **Chipset:** Optimized for the **9603N** SBD transceiver.
* **Power Requirements:** Requires a stable **5V DC** supply.
* **Logic:** Handles **Short Burst Data (SBD)** protocols, managing the "store-and-forward" sequence to ensure telemetry reaches European ground stations even with intermittent orbital visibility.

### 2. D-Orbit ION Bus Integration
* **Interface:** Assumes a physical **RS-422** or **High-Speed UART** (TTL) connection provided by the D-Orbit ION carrier.
* **Protocol:** Implements the **TEP Orbital Protocol**. Unlike standard transparent relays, the satellite acts as an active node that validates the packet's **Proof-of-History hash** in orbit before authorizing the downlink to the European Ground Station.

### 3. Galileo HAS Receiver
* **Frequency Tracking:** Hardware must be capable of tracking the **Galileo E6** frequency.
* **Functionality:** Enables the "Ship-Master" to receive high-accuracy encrypted command updates and Emergency Warning Services (EWS) directly from the constellation, bypassing the need for a standard terrestrial or cellular data link.


---

## TEP for Satellite Links

The **Transport Encrypted Protocol (TEP)** provides structural advantages specifically for the constraints of maritime and orbital communications:

> ### Zero Overhead
> TEP packets discard standard, bulky IP headers. By utilizing a minimalist encapsulation, the system saves precious bytes in **Short Burst Data (SBD)** transmissions, where every byte impacts latency and operational cost.

> ### Asynchronous Trust
> In the event of a total satellite link failure (e.g., during severe storms), the **TEP ledger** on the Ship-Master maintains the chronological sequence of all tag events. Once the link is restored, the D-Orbit satellite verifies the entire "missing" chain via its integrated ledger node, ensuring no data was tampered with during the blackout period.