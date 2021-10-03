"""Stats commands."""
import logging
from typing import Any, Dict

from ..events import StatsEvent
from .base import VacuumEmitter, _NoArgsCommand

_LOGGER = logging.getLogger(__name__)


class GetStats(_NoArgsCommand):
    """Get stats command."""

    name = "getStats"

    @classmethod
    def _handle_body_data_dict(
        cls, events: VacuumEmitter, data: Dict[str, Any]
    ) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        stats_event = StatsEvent(
            data.get("area"),
            data.get("cid"),
            data.get("time"),
            data.get("type"),
            data.get("start"),
        )
        events.stats.notify(stats_event)
        return True
