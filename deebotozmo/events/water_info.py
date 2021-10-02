"""Water info event module."""
from dataclasses import dataclass


@dataclass
class WaterInfoEvent:
    """Water info event representation."""

    mop_attached: bool
    amount: str
