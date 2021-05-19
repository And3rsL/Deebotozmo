from dataclasses import dataclass
from typing import Optional, List


@dataclass
class StatsEvent:
    area: Optional[int]
    cid: Optional[str]
    time: Optional[int]
    type: Optional[str]
    start: Optional[int]


@dataclass
class ErrorEvent:
    code: int
    description: Optional[str]


@dataclass
class FanSpeedEvent:
    speed: str


@dataclass
class BatteryEvent:
    value: int


@dataclass
class StatusEvent:
    available: bool
    state: str


@dataclass
class LifeSpanEvent:
    type: str
    percent: float


@dataclass
class WaterInfoEvent:
    mopAttached: bool
    amount: Optional[str]


@dataclass
class CleanLogEntry:
    timestamp: Optional[int]
    imageUrl: Optional[str]
    type: Optional[str]
    area: Optional[int]
    stopReason: Optional[str]
    totalTime: Optional[int]


@dataclass
class CleanLogEvent:
    logs: List[CleanLogEntry]
