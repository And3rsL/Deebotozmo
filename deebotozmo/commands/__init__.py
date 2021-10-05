"""Commands module."""
from typing import Dict, List, Type

from .base import Command, CommandWithHandling, SetCommand
from .battery import GetBattery
from .charge import Charge
from .charge_state import GetChargeState
from .clean import Clean, CleanArea, GetCleanInfo
from .clean_logs import GetCleanLogs
from .error import GetError
from .fan_speed import FanSpeedLevel, GetFanSpeed, SetFanSpeed
from .life_span import GetLifeSpan
from .map import (
    GetCachedMapInfo,
    GetMajorMap,
    GetMapSet,
    GetMapSubSet,
    GetMapTrace,
    GetMinorMap,
    GetPos,
)
from .play_sound import PlaySound
from .relocation import SetRelocationState
from .stats import GetStats
from .water_info import GetWaterInfo, SetWaterInfo, WaterLevel

# fmt: off
# ordered by file asc
_COMMANDS: List[Type[CommandWithHandling]] = [
    GetBattery,

    Charge,

    GetChargeState,

    Clean,
    CleanArea,
    GetCleanInfo,

    GetCleanLogs,

    GetError,

    GetFanSpeed,
    SetFanSpeed,

    GetLifeSpan,

    PlaySound,

    SetRelocationState,

    GetStats,

    GetWaterInfo,
    SetWaterInfo,
]
# fmt: on

COMMANDS: Dict[str, Type[CommandWithHandling]] = {cmd.name: cmd for cmd in _COMMANDS}

SET_COMMAND_NAMES: List[str] = [
    cmd.name for cmd in COMMANDS.values() if issubclass(cmd, SetCommand)
]

MAP_COMMANDS: List[Type[Command]] = [
    GetMajorMap,
    GetMapSet,
    GetMinorMap,
    GetPos,
    GetMapTrace,
    GetMapSubSet,
    GetCachedMapInfo,
]
