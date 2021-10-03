"""Commands module."""
from typing import Dict, List, Type

from .base import Command, SetCommand
from .battery import GetBattery
from .charge_state import GetChargeState
from .fan_speed import FanSpeedLevel, GetFanSpeed, SetFanSpeed
from .life_span import GetLifeSpan
from .stats import GetStats
from .water_info import GetWaterInfo, SetWaterInfo, WaterLevel

# fmt: off
# ordered by file asc
_COMMANDS: List[Type[Command]] = [
    GetBattery,

    GetChargeState,

    GetFanSpeed,
    SetFanSpeed,

    GetLifeSpan,

    GetStats,

    GetWaterInfo,
    SetWaterInfo,
]
# fmt: on

COMMANDS: Dict[str, Type[Command]] = {cmd.name: cmd for cmd in _COMMANDS}  # type: ignore

SET_COMMAND_NAMES: List[str] = [
    cmd.name for cmd in COMMANDS.values() if issubclass(cmd, SetCommand)
]
