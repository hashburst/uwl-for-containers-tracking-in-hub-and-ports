from __future__ import annotations

import numpy as np


class Kalman2D:
    """Simple constant-velocity Kalman filter for 2D position.

    State: [x, y, vx, vy]
    Measurement: [x, y]

    This is intentionally small and dependency-free (NumPy only).
    """

    def __init__(self, dt: float = 1.0, process_noise: float = 0.1, measurement_noise: float = 5.0):
        self.dt = float(dt)

        self.x = np.zeros((4, 1), dtype=np.float64)

        self.F = np.array(
            [[1, 0, self.dt, 0], [0, 1, 0, self.dt], [0, 0, 1, 0], [0, 0, 0, 1]],
            dtype=np.float64,
        )
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)

        self.Q = np.eye(4, dtype=np.float64) * float(process_noise)
        self.R = np.eye(2, dtype=np.float64) * float(measurement_noise)
        self.P = np.eye(4, dtype=np.float64)

    def predict(self) -> None:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, z_xy: tuple[float, float]) -> None:
        z = np.array([[float(z_xy[0])], [float(z_xy[1])]], dtype=np.float64)
        y = z - (self.H @ self.x)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + (K @ y)
        self.P = self.P - (K @ self.H @ self.P)

    @property
    def pos(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[1])
