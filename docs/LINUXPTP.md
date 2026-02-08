# PTP Synchronization on Raspberry Pi Anchors (linuxptp, ptp4l + phc2sys) in Layer-2 Mode

For TDoA localization you need multiple anchors to share a common time base.
`linuxptp` can synchronize the **PHC** (PTP Hardware Clock) of each NIC using IEEE 1588 PTP.

This guide focuses on **Layer-2 transport** (no UDP/IP), which fits well with raw-socket / EtherType protocols.

## 1) Install linuxptp

```bash
sudo apt update
sudo apt install linuxptp
```

Tools:
- `ptp4l`: synchronizes PHC across nodes
- `phc2sys`: optionally syncs system time (`CLOCK_REALTIME`) from PHC

## 2) Verify hardware timestamping support

```bash
sudo apt install ethtool
ethtool -T eth0
```

You want to see RX/TX hardware timestamp support.

## 3) Create a ptp4l config for Layer-2 transport

Create `/etc/linuxptp/uwl_ptp.cfg`:

```ini
[global]
network_transport    L2
delay_mechanism      E2E

# Announce once per second
logAnnounceInterval  0

# Sync frequency: -3 means 8 sync messages per second
logSyncInterval     -3

# Log level can be adjusted at runtime with -l
[eth0]
```

## 4) Start ptp4l

### Option A: a dedicated Grandmaster (recommended)

Pick one device (server/clock appliance/GNSS clock) as the grandmaster.

On the grandmaster:

```bash
sudo ptp4l -i eth0 -f /etc/linuxptp/uwl_ptp.cfg -m -l 7
```

On each anchor:

```bash
sudo ptp4l -i eth0 -f /etc/linuxptp/uwl_ptp.cfg -m -l 7
```

Anchors should automatically become slaves if they detect a better master.

### Option B: Best Master Clock Algorithm only

If you don’t enforce a single master, PTP will elect one.
This is acceptable for lab environments but less deterministic in production.

## 5) Sync system clock from PHC (optional)

If your applications read system time rather than PHC time, run:

```bash
sudo phc2sys -s eth0 -c CLOCK_REALTIME -w -m
```

- `-s eth0`: PHC source from eth0
- `-c CLOCK_REALTIME`: set system clock
- `-w`: wait until ptp4l is in sync

## 6) Monitor synchronization quality

While ptp4l runs you will see logs like:

- `master offset ...`
- `path delay ...`

After convergence, the offset should stabilize (often tens to hundreds of ns depending on hardware, topology, and load).

## 7) Operational notes for ports/industrial yards

- Use **wired Ethernet** for anchors (PoE is ideal).
- Keep PTP traffic on a dedicated VLAN or isolated switch if possible.
- For better stability: quality switch, fixed link speed, minimal congestion.
- If you need sub-100ns stability consistently, consider a clock appliance / GNSS-disciplined master.

## Next

- Use `SO_TIMESTAMPING` to collect hardware RX timestamps in your raw-socket receiver (`HW_TIMESTAMP_RECVMSG.md`).
- Feed synced timestamps into your TDoA multilateration (`TDOA_MULTILATERATION.md`).
