"""Life span commands."""
import logging
from enum import Enum, unique
from typing import List

from ..events import LifeSpanEvent
from .base import CommandWithHandling, VacuumEmitter

_LOGGER = logging.getLogger(__name__)


@unique
class LifeSpan(str, Enum):
    """Enum class for all possible life span components."""

    SIDE_BRUSH = "sideBrush"
    BRUSH = "brush"
    FILTER = "heap"


class GetLifeSpan(CommandWithHandling):
    """Get life span command."""

    name = "getLifeSpan"

    def __init__(self) -> None:
        args = [life_span.value for life_span in LifeSpan]
        super().__init__(args)

    @classmethod
    def _handle_body_data_list(cls, events: VacuumEmitter, data: List) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        handle_all_components = True
        components: LifeSpanEvent = {}
        for component in data:
            try:
                component_type = LifeSpan(component.get("type"))
            except (ValueError, KeyError):
                _LOGGER.warning(
                    "Could not identify component type: event=%s", data, exc_info=True
                )
                handle_all_components = False
                continue

            left = int(component.get("left", 0))
            total = int(component.get("total", 0))

            if component_type and total > 0:
                percent = round((left / total) * 100, 2)
                components[component_type.value] = percent  # type: ignore
            else:
                _LOGGER.warning("Could not parse life span event with %s", data)
                handle_all_components = False
                continue

        if components:
            events.lifespan.notify(components)

        return handle_all_components
