from __future__ import annotations

from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class Measurement(BaseModel):
    """Single anchor measurement for a given tag.
    - rssi_dbm: received signal strength at anchor (dBm)
    - toa_ns: time of arrival at anchor, in *anchor-local* clock (nanoseconds)
    """
    anchor_id: str
    tag_id: str
    t_rx_unix_ms: int = Field(..., description="Reception time at anchor, Unix epoch in ms")
    rssi_dbm: Optional[float] = None
    toa_ns: Optional[int] = None
    channel: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class UwlPayload(BaseModel):
    kind: Literal["UWL_MEASUREMENT_BATCH"] = "UWL_MEASUREMENT_BATCH"
    gateway_id: str
    seq: int
    sent_unix_ms: int
    measurements: list[Measurement]


class TagPosition(BaseModel):
    tag_id: str
    x_m: float
    y_m: float
    method: Literal["RSSI_LS", "TDOA_LS"]
    quality: float = Field(..., description="0..1 heuristic confidence")
    computed_unix_ms: int
