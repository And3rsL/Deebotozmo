"""Deebot events."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict

from deebotozmo.models import Room, VacuumState


@dataclass
class BatteryEvent:
    """Battery event representation."""

    value: int


@dataclass
class CleanLogEntry:
    """Clean log entry representation."""

    timestamp: Optional[int]
    image_url: Optional[str]
    type: Optional[str]
    area: Optional[int]
    stop_reason: Optional[str]
    # Stop reason
    # 1 -> finished
    # 2 -> manual stopped
    # 3 -> finished with warnings (ex. a scheduled room was not cleaned)
    total_time: Optional[int]  # in seconds


@dataclass
class CleanLogEvent:
    """Clean log event representation."""

    logs: List[CleanLogEntry]


@dataclass
class ErrorEvent:
    """Error event representation."""

    code: int
    description: Optional[str]


@dataclass
class FanSpeedEvent:
    """Fan speed event representation."""

    speed: str


class LifeSpanEvent(TypedDict, total=False):
    """Life span event representation.

    Must be in sync with the enum :class:`~LifeSpan`.
    """

    sideBrush: float
    brush: float
    filter: float


@dataclass
class MapEvent:
    """Map event representation."""


@dataclass
class RoomsEvent:
    """Room event representation."""

    rooms: List[Room]


@dataclass
class StatsEvent:
    """Stats event representation."""

    area: Optional[int]
    clean_id: Optional[str]
    time: Optional[int]
    type: Optional[str]
    start: Optional[int]


@dataclass
class StatusEvent:
    """Status event representation."""

    available: bool
    state: Optional[VacuumState]


@dataclass
class WaterInfoEvent:
    """Water info event representation."""

    mop_attached: bool
    amount: str


@dataclass
class CustomCommandEvent:
    """Custom command event representation."""

    name: str
    response: Dict[str, Any]
