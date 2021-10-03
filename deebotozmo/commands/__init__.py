"""Commands module."""
from typing import Dict, List, Type

from .base import Command, SetCommand
from .fan_speed import FanSpeedLevel, GetFanSpeed, SetFanSpeed
from .water_info import GetWaterInfo, SetWaterInfo, WaterLevel

# fmt: off
_COMMANDS: List[Type[Command]] = [
    GetWaterInfo,
    SetWaterInfo,

    GetFanSpeed,
    SetFanSpeed
]
# fmt: on

COMMANDS: Dict[str, Type[Command]] = {cmd.name: cmd for cmd in _COMMANDS}  # type: ignore

SET_COMMAND_NAMES: List[str] = [
    cmd.name for cmd in COMMANDS.values() if issubclass(cmd, SetCommand)
]
