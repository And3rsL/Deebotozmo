"""Event module."""
from dataclasses import dataclass

from deebotozmo.event_emitter import EventEmitter

from .fan_speed import FanSpeedEvent
from .water_info import WaterInfoEvent


@dataclass
class Events:
    """Class to combine all different events."""

    water_info: EventEmitter[WaterInfoEvent]
    fan_speed: EventEmitter[FanSpeedEvent]
