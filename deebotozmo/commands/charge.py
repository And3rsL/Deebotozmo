"""Charge commands."""
import logging
from typing import Any, Dict

from ..events import StatusEvent
from ..models import VacuumState
from .base import VacuumEmitter, _ExecuteCommand

_LOGGER = logging.getLogger(__name__)


class Charge(_ExecuteCommand):
    """Charge command."""

    name = "charge"

    def __init__(self) -> None:
        super().__init__({"act": "go"})

    @classmethod
    def _handle_body(cls, events: VacuumEmitter, body: Dict[str, Any]) -> bool:
        """Handle message->body and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        success = super()._handle_body(events, body)
        if success:
            events.status.notify(StatusEvent(True, VacuumState.RETURNING))

        return success
