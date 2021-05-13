from dataclasses import dataclass
from typing import Optional


@dataclass
class StatsEvent:
    area: Optional[int]
    cid: Optional[str]
    time: Optional[int]
    type: Optional[str]
    content: Optional[str]


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
    mop_attached: bool
    amount: Optional[str]
