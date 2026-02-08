# Kalman Filtering for Position Smoothing (Port / Multipath)

In a container yard, RF measurements suffer from:
- multipath reflections off metal
- partial occlusion
- transient interference

This often yields noisy `(x,y)` estimates with sudden jumps. A Kalman filter can smooth these outputs by combining:
- a motion model (position + velocity)
- noisy measurements from the localization solver

## State model (2D constant velocity)

State vector:

- `x = [px, py, vx, vy]^T`

Time step: `dt` (seconds)

State transition:

```
px' = px + vx*dt
py' = py + vy*dt
vx' = vx
vy' = vy
```

Measurement vector:

- `z = [px, py]^T`

## Minimal implementation

A small implementation is provided in:

- `extras/dashboard_flask/kalman.py`

It supports:

- `predict()` step
- `update(z)` step

## Tuning guidance

Two main parameters:
- **Process noise (Q)**: how much you believe the object can accelerate/change direction unexpectedly.
- **Measurement noise (R)**: how noisy the localization output is.

Port yard defaults:
- Start with higher `R` (measurements are often noisy)
- Increase `Q` if you see lag behind real motion

## Outlier handling (recommended)

A Kalman filter alone can be misled by extreme outliers. Add:
- residual gating (ignore updates when |innovation| is too large)
- anchor-quality thresholds (require >= 3 anchors; reject high residuals)
- median filtering over a short window before Kalman update

## Where to apply it

- On the dashboard (operator-friendly smoothing)
- On the server side (track storage and downstream consumers)
- In per-tag tracking pipelines with event-driven updates
