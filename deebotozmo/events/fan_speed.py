"""(fan) speed event module."""
from dataclasses import dataclass


@dataclass
class FanSpeedEvent:
    """Fan speed event representation."""

    speed: str
