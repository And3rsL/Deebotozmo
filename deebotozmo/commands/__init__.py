"""Commands module."""
from typing import Dict, Type

from .base import Command, SetCommand  # noqa: F401
from .water_info import GetWaterInfo, SetWaterInfo

COMMANDS: Dict[str, Type[Command]] = {
    GetWaterInfo.name: GetWaterInfo,
    SetWaterInfo.name: SetWaterInfo,
}
