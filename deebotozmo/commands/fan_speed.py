"""(fan) speed commands."""
import logging
from enum import unique
from typing import Any, Dict, Mapping, Union

from deebotozmo.commands import SetCommand
from deebotozmo.commands.base import DisplayNameEnum, GetCommand
from deebotozmo.event_emitter import VacuumEmitter
from deebotozmo.events import FanSpeedEvent

_LOGGER = logging.getLogger(__name__)


@unique
class FanSpeedLevel(DisplayNameEnum):
    """Enum class for all possible fan speed levels."""

    NORMAL = 0
    MAX = 1
    MAX_PLUS = 2, "max+"
    QUIET = 1000


class GetFanSpeed(GetCommand):
    """Get fan speed command."""

    name = "getSpeed"

    @classmethod
    def _handle_body_data(cls, events: VacuumEmitter, data: Dict[str, Any]) -> bool:
        """Handle body data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        speed = data.get("speed", None)

        if speed is not None:
            try:
                events.fan_speed.notify(
                    FanSpeedEvent(FanSpeedLevel(int(speed)).display_name)
                )
                return True
            except ValueError:
                _LOGGER.warning("Could not parse correctly fan speed: %s", data)

        _LOGGER.warning("Could not parse %s with %s", cls.name, data)
        return False


class SetFanSpeed(SetCommand):
    """Set fan speed command."""

    name = "setSpeed"
    get_command = GetFanSpeed

    def __init__(
        self, speed: Union[str, int, FanSpeedLevel], **kwargs: Mapping[str, Any]
    ) -> None:
        if isinstance(speed, str):
            speed = FanSpeedLevel.get(speed)
        if isinstance(speed, FanSpeedLevel):
            speed = speed.value

        super().__init__({"speed": speed}, [], **kwargs)
