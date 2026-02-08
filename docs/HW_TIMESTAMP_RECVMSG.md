# Receiving Ethernet Frames with Hardware PTP Timestamps (recvmsg + SO_TIMESTAMPING)

This note shows how to receive a Layer-2 (AF_PACKET) frame and extract the **hardware RX timestamp** provided by the Linux kernel when NIC timestamping is enabled.

The key idea:
- Use `sock.recvmsg()` (not `recv()`)
- Enable `SO_TIMESTAMPING`
- Parse ancillary data (`ancdata`) to get a hardware timestamp in nanoseconds

## 1) Requirements

- NIC + driver that supports hardware timestamping
- `linuxptp` or equivalent PTP sync (recommended for TDoA across multiple anchors)
- Root / `CAP_NET_RAW`

Check timestamping capabilities:

```bash
sudo apt update
sudo apt install ethtool
ethtool -T eth0
```

Look for support flags such as hardware receive timestamping.

## 2) Enable SO_TIMESTAMPING on the socket

Linux uses `SO_TIMESTAMPING` to request timestamp metadata for incoming packets.

Example configuration:

```python
import socket
import struct

SO_TIMESTAMPING = 37

SOF_TIMESTAMPING_RX_HARDWARE = (1 << 2)
SOF_TIMESTAMPING_RAW_HARDWARE = (1 << 6)

def enable_hw_rx_timestamping(sock: socket.socket) -> None:
    flags = SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_RAW_HARDWARE
    sock.setsockopt(socket.SOL_SOCKET, SO_TIMESTAMPING, struct.pack("I", flags))
```

Note: some kernels/drivers may also use software timestamps; you want the **hardware** one.

## 3) Receive with recvmsg() and parse ancillary data

`recvmsg()` returns `(data, ancdata, msg_flags, address)`.

- `data` contains the Ethernet frame (header + payload)
- `ancdata` contains control messages (including timestamping)

Example:

```python
import socket
import struct
from typing import Optional, Tuple

SO_TIMESTAMPING = 37  # Linux constant

def recv_frame_with_hwts(sock: socket.socket, bufsize: int = 4096, cmsg_size: int = 1024) -> Tuple[bytes, Optional[int]]:
    data, ancdata, flags, addr = sock.recvmsg(bufsize, cmsg_size)
    hw_ts_ns: Optional[int] = None

    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level == socket.SOL_SOCKET and cmsg_type == SO_TIMESTAMPING:
            # Linux SCM_TIMESTAMPING provides 3 timestamps:
            #   [0] software
            #   [1] (often unused)
            #   [2] hardware (raw)
            #
            # The structure is 3 timespec structs (sec, nsec).
            # On many systems this maps to 6 64-bit integers.
            #
            # If unpacking fails on your target, inspect len(cmsg_data)
            # and adjust the format accordingly.
            ts = struct.unpack("6Q", cmsg_data[:48])
            sec = ts[4]
            nsec = ts[5]
            if sec != 0 or nsec != 0:
                hw_ts_ns = sec * 1_000_000_000 + nsec

    return data, hw_ts_ns
```

### Extracting the Ethernet payload

Ethernet header is 14 bytes:

- Dest MAC (6)
- Src MAC (6)
- EtherType (2)

```python
def split_eth_frame(frame: bytes) -> tuple[bytes, bytes]:
    eth_header = frame[:14]
    payload = frame[14:]
    return eth_header, payload
```

## 4) Common pitfalls

- **No timestamps**: driver/NIC may not support HW timestamping, or PTP is not configured.
- **Wrong unpack format**: kernel structures can differ across arch/kernel. Validate `len(cmsg_data)` and adjust unpacking.
- **Clock domain**: the hardware timestamp is from the NIC clock (PHC). You typically sync PHCs across anchors with `ptp4l`.

## 5) How this is used in UWB/TEP anchor networks

- UWB provides **RF ToA** at the anchor.
- Ethernet hardware timestamping provides **precise arrival time** of frames on the wired backhaul.
- For TDoA, you must compare timestamps between anchors, which requires **PTP** (see `LINUXPTP.md`).
