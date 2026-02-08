"""TDoA (hyperbolic multilateration) utilities.

This module converts synchronized hardware receive timestamps from multiple
anchors into an (x, y) estimate in a local cartesian coordinate system.

Implementation notes
- Uses an iterative damped Gauss-Newton solver (NumPy only).
- Suitable for "yard coordinates" (meters). Convert to GPS in a later mapping layer.

Math
Given anchors a0..aN with known 2D positions, and synchronized hardware
receive timestamps t0..tN (nanoseconds), we can compute distance-differences
relative to a reference anchor a0:

  di0 = c * (ti - t0)

where c is the speed of light in m/s and ti are in seconds.
The unknown tag position p satisfies:

  ||p - ai|| - ||p - a0|| = di0

for i = 1..N.

We solve for p by minimizing the residuals with damped Gauss-Newton.

Important
This is not a full UWB stack; it assumes you already have high-quality,
synchronized ToA timestamps. In practice you will also:
- Calibrate per-anchor antenna delays.
- Filter out NLOS/multipath outliers.
- Run a Kalman filter on the resulting positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

C_M_PER_S = 299_792_458.0


@dataclass(frozen=True)
class Anchor:
    anchor_id: str
    x_m: float
    y_m: float


def calculate_distance_diff_m(ts_a_ns: int, ts_b_ns: int) -> float:
    """Return path-length difference in meters from two synchronized timestamps.

    Delta_D = |Delta_t| * c
    where Delta_t is in seconds.
    """

    delta_t_ns = abs(int(ts_b_ns) - int(ts_a_ns))
    return (delta_t_ns * 1e-9) * C_M_PER_S


def _residuals_and_jacobian(p: np.ndarray, anchors: np.ndarray, ddi0: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute residual vector r and Jacobian J for the hyperbolic system."""

    # p: (2,), anchors: (K,2) with anchors[0] being reference
    ref = anchors[0]
    pr = p - ref
    d_ref = np.linalg.norm(pr) + 1e-12

    r_list: List[float] = []
    J_rows: List[np.ndarray] = []

    for i in range(1, anchors.shape[0]):
        ai = anchors[i]
        pi = p - ai
        d_i = np.linalg.norm(pi) + 1e-12

        # f_i(p) = ||p-ai|| - ||p-a0|| - ddi0[i-1]
        r_i = (d_i - d_ref) - ddi0[i - 1]
        r_list.append(float(r_i))

        # Gradient:
        # d/ dp (||p-ai||) = (p-ai)/||p-ai||
        # d/ dp (||p-a0||) = (p-a0)/||p-a0||
        grad = (pi / d_i) - (pr / d_ref)
        J_rows.append(grad.reshape(1, 2))

    r = np.array(r_list, dtype=np.float64).reshape(-1, 1)  # (K-1,1)
    J = np.vstack(J_rows).astype(np.float64)  # (K-1,2)
    return r, J


def tdoa_localize_xy(
    anchors: Iterable[Anchor],
    timestamps_ns: Dict[str, int],
    *,
    ref_anchor_id: Optional[str] = None,
    max_iter: int = 30,
    damping: float = 1e-2,
    tol: float = 1e-6,
) -> Tuple[float, float]:
    """Estimate (x, y) from synchronized ToA timestamps.

    Parameters
    - anchors: iterable of Anchor with known positions.
    - timestamps_ns: mapping {anchor_id: hw_timestamp_ns} for the same UWB "event".
    - ref_anchor_id: if set, uses that anchor as reference; otherwise first available.
    - max_iter: Gauss-Newton iterations.
    - damping: Levenberg-like diagonal damping term.
    - tol: stop when update norm < tol.

    Returns
    - (x_m, y_m)

    Raises
    - ValueError if fewer than 3 anchors with timestamps are provided.
    """

    anchors_list = [a for a in anchors if a.anchor_id in timestamps_ns]
    if len(anchors_list) < 3:
        raise ValueError("Need at least 3 anchors with timestamps for 2D TDoA")

    # Choose reference anchor
    if ref_anchor_id is None:
        ref_anchor_id = anchors_list[0].anchor_id

    anchors_list.sort(key=lambda a: 0 if a.anchor_id == ref_anchor_id else 1)
    if anchors_list[0].anchor_id != ref_anchor_id:
        raise ValueError("ref_anchor_id not present in provided anchors/timestamps")

    anchors_xy = np.array([[a.x_m, a.y_m] for a in anchors_list], dtype=np.float64)

    ref_ts = int(timestamps_ns[ref_anchor_id])
    ddi0: List[float] = []
    for a in anchors_list[1:]:
        dt_ns = int(timestamps_ns[a.anchor_id]) - ref_ts
        ddi0.append((dt_ns * 1e-9) * C_M_PER_S)
    ddi0_v = np.array(ddi0, dtype=np.float64).reshape(-1, 1)

    # Initial guess: centroid of anchors
    p = anchors_xy.mean(axis=0)

    for _ in range(max_iter):
        r, J = _residuals_and_jacobian(p, anchors_xy, ddi0_v)

        # Solve (J^T J + λI) Δ = -J^T r
        JTJ = J.T @ J
        A = JTJ + damping * np.eye(2)
        b = -(J.T @ r)
        try:
            delta = np.linalg.solve(A, b).reshape(2)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(A, b, rcond=None)[0].reshape(2)

        p_new = p + delta

        if float(np.linalg.norm(delta)) < tol:
            p = p_new
            break
        p = p_new

    return float(p[0]), float(p[1])
