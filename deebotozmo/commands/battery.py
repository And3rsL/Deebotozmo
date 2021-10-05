"""Battery commands."""
import logging
from typing import Any, Dict

from ..events import BatteryEvent
from .base import VacuumEmitter, _NoArgsCommand

_LOGGER = logging.getLogger(__name__)


class GetBattery(_NoArgsCommand):
    """Get battery command."""

    name = "getBattery"

    @classmethod
    def _handle_body_data_dict(
        cls, events: VacuumEmitter, data: Dict[str, Any]
    ) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        try:
            events.battery.notify(BatteryEvent(data["value"]))
        except ValueError:
            _LOGGER.warning("Couldn't parse battery status: %s", data)
        return True
