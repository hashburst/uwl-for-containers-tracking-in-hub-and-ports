# TEP over Layer-2 Raw Sockets on Raspberry Pi (Linux)

This note explains how to run a TEP-like protocol directly at **OSI Layer 2** using **raw Ethernet frames** (no IP address required), which reduces protocol overhead and makes the node much less visible to typical IP-based scans.

## Goals

- Send/receive **Ethernet frames** with a custom EtherType (TEP) using `AF_PACKET`
- Optionally keep the interface **without an IP address**
- Enable **promiscuous mode** for peer-to-peer frame collection
- Prepare the environment for **hardware timestamping** (PTP / SO_TIMESTAMPING) used by ToA/TDoA pipelines

## Prerequisites

- Raspberry Pi OS / Debian-based Linux
- Root privileges (raw sockets require `CAP_NET_RAW`)
- Ethernet recommended (`eth0`) for deterministic timestamps

## 1) Put the interface in "no IP" (optional)

If you want the node to be reachable only via Layer-2 frames (no TCP/UDP services):

```bash
sudo ip addr flush dev eth0
sudo ip link set eth0 up
```

If you use NetworkManager, you can set the connection to **manual** (no IPv4/IPv6) or mark the device unmanaged.
On systemd-networkd, use `DHCP=no` and omit static addresses.

Note: even with no IP address, the NIC still has a **MAC address** and can transmit/receive Ethernet frames.

## 2) Enable promiscuous mode (optional but common for P2P)

Promiscuous mode allows the Pi to receive frames not addressed to its MAC (useful in some broadcast / discovery or P2P designs):

```bash
sudo ip link set eth0 promisc on
```

Disable later with:

```bash
sudo ip link set eth0 promisc off
```

## 3) Choose a custom EtherType for TEP

EtherType is a 16-bit field in the Ethernet header. For experiments you can use a local/private value.
In the codebase we use:

- `TEP_ETHERTYPE = 0x88B5` (example)

All peers that participate in the protocol must agree on the EtherType.

## 4) Python: open a Layer-2 socket (AF_PACKET)

This is the minimal setup to receive Ethernet frames:

```python
import socket

TEP_ETHERTYPE = 0x88B5

sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(TEP_ETHERTYPE))
sock.bind(("eth0", 0))
```

### Sending a frame

You must build an Ethernet header:

- Destination MAC (6 bytes)
- Source MAC (6 bytes)
- EtherType (2 bytes)
- Payload (your encrypted TEP payload)

Example:

```python
import struct

def mac_to_bytes(mac: str) -> bytes:
    return bytes(int(b, 16) for b in mac.split(":"))

def send_tep_frame(sock, dest_mac: str, src_mac: str, payload: bytes):
    ethertype = 0x88B5
    frame = struct.pack("!6s6sH", mac_to_bytes(dest_mac), mac_to_bytes(src_mac), ethertype) + payload
    sock.send(frame)
```

In practice you will usually:
- Broadcast frames (`ff:ff:ff:ff:ff:ff`) for discovery, or
- Use unicast MACs once peers are known.

## 5) Permissions / capabilities

Raw sockets require privileges.

Option A (simplest): run as root:

```bash
sudo python your_script.py
```

Option B: grant capabilities to the interpreter (be careful in production):

```bash
sudo setcap cap_net_raw,cap_net_admin+eip $(readlink -f $(which python3))
```

## 6) Why this helps TEP-like designs

- **Lower overhead**: Ethernet header is small compared to TCP/IP stacks.
- **Reduced attack surface**: without IP, typical scanners (nmap/ping) do not see the node.
- **Deterministic timing**: fewer layers can reduce jitter for ToA/TDoA processing.
- **Compatibility with PTP**: you can run PTP in L2 mode and use hardware timestamps from the NIC.

## 7) Where UWB fits

UWB ranging uses short impulses across a **very wide** spectrum (often within multi-GHz bands depending on region/regulation). In many deployments, UWB operates in bands around **6.5–9 GHz**.

From a system perspective:
- UWB is used for **ranging / ToA/TDoA** at the RF level.
- Ethernet (raw sockets) can be used as the **wired backhaul** among anchors and the server, and as the transport for “TEP frames”.

UWB’s wideband nature typically makes narrowband jamming harder, but always assume an attacker can increase power or use broadband jammers; design with monitoring and redundancy.

## Next

See:
- `HW_TIMESTAMP_RECVMSG.md` for `recvmsg()` + `SO_TIMESTAMPING`
- `LINUXPTP.md` for `ptp4l`/`phc2sys` in Layer-2 mode
