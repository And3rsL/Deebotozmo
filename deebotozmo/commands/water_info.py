"""Water info commands."""
import logging
from typing import Any, Dict, Mapping

from ..events import WaterInfoEvent, WaterLevel
from .base import Events, GetCommand, SetCommand
from .util import get_member

_LOGGER = logging.getLogger(__name__)


class GetWaterInfo(GetCommand):
    """Get water info command."""

    name = "getWaterInfo"

    @classmethod
    def _handle_body_data(cls, events: Events, data: Dict[str, Any]) -> None:
        amount = data.get("amount", None)
        mop_attached = bool(data.get("enable"))

        if amount:
            try:
                events.water_info.notify(
                    WaterInfoEvent(mop_attached, WaterLevel(int(amount)))
                )
            except ValueError:
                _LOGGER.warning("Could not parse correctly water info amount: %s", data)
        else:
            _LOGGER.warning("Could not parse water info event with %s", data)


class SetWaterInfo(SetCommand):
    """Set water info command."""

    name = "setWaterInfo"
    get_command = GetWaterInfo

    def __init__(self, amount: str, **kwargs: Mapping[str, Any]) -> None:
        # removing "enable" as we don't can set it
        remove_from_kwargs = ["enable"]
        super().__init__(
            {"amount": get_member(WaterLevel, amount), "enable": 0},
            remove_from_kwargs,
            **kwargs
        )
