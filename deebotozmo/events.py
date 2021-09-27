"""Deebot events."""

from dataclasses import dataclass
from typing import List, Optional

from deebotozmo.models import Room, VacuumState


@dataclass
class StatsEvent:
    """Stats event representation."""

    area: Optional[int]
    clean_id: Optional[str]
    time: Optional[int]
    type: Optional[str]
    start: Optional[int]


@dataclass
class ErrorEvent:
    """Error event representation."""

    code: int
    description: Optional[str]


@dataclass
class FanSpeedEvent:
    """Fan speed event representation."""

    speed: str


@dataclass
class BatteryEvent:
    """Battery event representation."""

    value: int


@dataclass
class StatusEvent:
    """Status event representation."""

    available: bool
    state: Optional[VacuumState]


@dataclass
class LifeSpanEvent:
    """Lifespan event representation."""

    type: str
    percent: float


@dataclass
class WaterInfoEvent:
    """Water info event representation."""

    mopAttached: bool
    amount: Optional[str]


@dataclass
class CleanLogEntry:
    """Clean log entry representation."""

    timestamp: Optional[int]
    imageUrl: Optional[str]
    type: Optional[str]
    area: Optional[int]
    stopReason: Optional[str]
    # Stop reason
    # 1 -> finished
    # 2 -> manual stopped
    # 3 -> finished with warnings (ex. a scheduled room was not cleaned)
    totalTime: Optional[int]  # in seconds


@dataclass
class CleanLogEvent:
    """Clean log event representation."""

    logs: List[CleanLogEntry]


@dataclass
class RoomsEvent:
    """Room event representation."""

    rooms: List[Room]


@dataclass
class MapEvent:
    """Map event representation."""

    pass
