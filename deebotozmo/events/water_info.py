"""Water info event module."""
from dataclasses import dataclass
from enum import IntEnum, unique


@unique
class WaterLevel(IntEnum):
    """Enum class for all possible water levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    ULTRAHIGH = 4


@dataclass
class WaterInfoEvent:
    """Water info event representation."""

    mop_attached: bool
    amount: WaterLevel
