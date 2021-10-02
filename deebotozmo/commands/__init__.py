"""Commands module."""
from typing import Dict, List, Type

from .base import Command, SetCommand
from .water_info import GetWaterInfo, SetWaterInfo

COMMANDS: Dict[str, Type[Command]] = {
    GetWaterInfo.name: GetWaterInfo,
    SetWaterInfo.name: SetWaterInfo,
}

SET_COMMAND_NAMES: List[str] = [
    cmd.name for cmd in COMMANDS.values() if issubclass(cmd, SetCommand)
]
