"""Water info commands."""
import logging
from typing import Any, Dict, Mapping, Union

from ..events import WaterInfoEvent, WaterLevel
from .base import Events, GetCommand, SetCommand
from .util import get_member

_LOGGER = logging.getLogger(__name__)


class GetWaterInfo(GetCommand):
    """Get water info command."""

    name = "getWaterInfo"

    @classmethod
    def _handle_body_data(cls, events: Events, data: Dict[str, Any]) -> bool:
        """Handle body data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        amount = data.get("amount", None)
        mop_attached = bool(data.get("enable"))

        if amount:
            try:
                events.water_info.notify(
                    WaterInfoEvent(mop_attached, WaterLevel(int(amount)))
                )
                return True
            except ValueError:
                _LOGGER.warning("Could not parse correctly water info amount: %s", data)

        _LOGGER.warning("Could not parse water info event with %s", data)
        return False


class SetWaterInfo(SetCommand):
    """Set water info command."""

    name = "setWaterInfo"
    get_command = GetWaterInfo

    def __init__(
        self, amount: Union[str, int, WaterLevel], **kwargs: Mapping[str, Any]
    ) -> None:
        # removing "enable" as we don't can set it
        remove_from_kwargs = ["enable"]
        if isinstance(amount, (str, WaterLevel)):
            amount = get_member(WaterLevel, amount)

        super().__init__({"amount": amount, "enable": 0}, remove_from_kwargs, **kwargs)
