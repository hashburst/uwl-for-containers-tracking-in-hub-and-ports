# Hyperbolic Multilateration (TDoA) to Estimate (X, Y)

In TDoA localization, each anchor provides a timestamp for the same emission.
Anchors are synchronized; the tag/transmitter is not.

Using one anchor as a reference (index 0), each other anchor i yields:

- measured distance difference: `Δd_i = c * (t_i - t_0)`
- geometric distance difference from a candidate position `p = (x, y)`:
  `f_i(p) = ||p - a_i|| - ||p - a_0||`

We estimate `p` by minimizing residuals:

- minimize over p: `r_i(p) = f_i(p) - Δd_i`

This is a non-linear least squares problem.

## Inputs

- Anchor positions `a_i = (x_i, y_i)` in meters, known/fixed
- Hardware timestamps `t_i` in nanoseconds for the same packet emission
- `c = 0.299792458 m/ns`

## A NumPy-only Gauss–Newton solver (with damping)

This implementation avoids SciPy to keep dependencies minimal.

```python
from __future__ import annotations
import numpy as np

C_METERS_PER_NS = 0.299792458

def tdoa_localize_xy(
    anchors_xy: np.ndarray,
    timestamps_ns: np.ndarray,
    ref_idx: int = 0,
    max_iter: int = 50,
    damping: float = 1e-3,
    tol: float = 1e-6,
) -> np.ndarray:
    """
    Estimate (x,y) from TDoA measurements using Gauss–Newton with damping.

    anchors_xy: shape (N,2)
    timestamps_ns: shape (N,)
    ref_idx: index of the reference anchor (usually 0)
    returns: shape (2,) position in meters
    """
    n = anchors_xy.shape[0]
    if n < 3:
        raise ValueError("Need at least 3 anchors for 2D TDoA localization")

    # Reorder so that ref is 0
    if ref_idx != 0:
        idx = np.arange(n)
        idx[0], idx[ref_idx] = idx[ref_idx], idx[0]
        anchors_xy = anchors_xy[idx]
        timestamps_ns = timestamps_ns[idx]

    a0 = anchors_xy[0]
    t0 = timestamps_ns[0]

    # Measured distance differences Δd_i for i>=1
    dd = (timestamps_ns[1:] - t0) * C_METERS_PER_NS  # shape (n-1,)

    # Initial guess: centroid of anchors
    p = anchors_xy.mean(axis=0).astype(float)

    for _ in range(max_iter):
        # Distances to anchors
        d0 = np.linalg.norm(p - a0) + 1e-12

        di = np.linalg.norm(p - anchors_xy[1:], axis=1) + 1e-12  # shape (n-1,)

        # Residuals: f_i(p) - Δd_i
        f = di - d0
        r = f - dd  # shape (n-1,)

        # Jacobian J: partial derivatives wrt x,y
        # ∂/∂p ||p-a|| = (p-a)/||p-a||
        grad_i = (p - anchors_xy[1:]) / di[:, None]          # shape (n-1,2)
        grad_0 = (p - a0) / d0                                # shape (2,)
        J = grad_i - grad_0[None, :]                          # shape (n-1,2)

        # Solve (J^T J + λI) Δ = -J^T r
        A = J.T @ J + damping * np.eye(2)
        b = -J.T @ r
        delta = np.linalg.solve(A, b)

        p_new = p + delta
        if np.linalg.norm(delta) < tol:
            p = p_new
            break
        p = p_new

    return p
```

## Usage example

```python
import numpy as np

anchors = np.array([
    [0.0, 0.0],
    [100.0, 0.0],
    [50.0, 80.0],
])

# Example: timestamps already synchronized by PTP
ts = np.array([
    1_707_234_567_000_000_000,
    1_707_234_567_000_000_120,
    1_707_234_567_000_000_050,
], dtype=np.int64)

pos = tdoa_localize_xy(anchors, ts)
print(pos)
```

## Practical considerations in a port environment

- **Multipath** from metal stacks can dominate error; apply filtering and outlier rejection.
- Use **more than 3 anchors** and solve in least-squares to reduce sensitivity.
- Add a motion model filter (Kalman) to smooth jitter (`KALMAN_FILTER.md`).
- Calibrate anchor delays and, when possible, use UWB’s native ranging reports rather than only backhaul timestamps.
