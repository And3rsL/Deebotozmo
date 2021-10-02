"""Event module."""
from dataclasses import dataclass

from deebotozmo.event_emitter import EventEmitter

from .water_info import WaterInfoEvent, WaterLevel  # noqa: F401


@dataclass
class Events:
    """Class to combine all different events."""

    water_info: EventEmitter[WaterInfoEvent]
