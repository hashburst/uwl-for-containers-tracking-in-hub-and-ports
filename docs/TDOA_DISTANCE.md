# TDoA: Convert Timestamp Differences to Distance Differences

In TDoA (Time Difference of Arrival), the transmitter is not time-synchronized with anchors.
Instead of absolute time-of-flight, anchors compare **arrival time differences** for the same emission.

Given two synchronized anchors A and B:

- `ts_a_ns`: hardware RX timestamp at anchor A (nanoseconds)
- `ts_b_ns`: hardware RX timestamp at anchor B (nanoseconds)

Then:

- `Δt_ns = ts_b_ns - ts_a_ns`
- Distance difference: `Δd = Δt * c`

Where `c` is the speed of propagation.

## Speed of light (approx.)

- `c = 299,792,458 m/s`
- In meters per nanosecond:

```text
c_ns ≈ 0.299792458 m/ns
```

## Python function

```python
C_METERS_PER_NS = 0.299792458

def distance_difference_m(ts_a_ns: int, ts_b_ns: int) -> float:
    """Return absolute distance difference (meters) implied by two synchronized RX timestamps."""
    delta_t_ns = abs(ts_b_ns - ts_a_ns)
    return delta_t_ns * C_METERS_PER_NS
```

## Notes for real deployments

1) **Clock synchronization**
- This only makes sense if anchors are synchronized (PTP, see `LINUXPTP.md`).

2) **Antenna / RF chain delays**
- Each anchor has a constant delay offset (PCB, antenna, analog front-end).
- You usually calibrate and subtract these offsets.

3) **Medium effects**
- Propagation speed in air varies slightly with humidity/temperature, but error is typically small compared to multipath.

4) **Interpretation**
- `Δd` is not a position; it defines a **hyperbola** of possible locations.
- With ≥3 anchors you solve for an (x,y) that best fits multiple `Δd` constraints (see `TDOA_MULTILATERATION.md`).
