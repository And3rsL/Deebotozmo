"""Clean commands."""
import logging
from enum import Enum, unique

from .base import _ExecuteCommand

_LOGGER = logging.getLogger(__name__)


@unique
class CleanAction(Enum):
    """Enum class for all possible clean actions."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


@unique
class CleanMode(Enum):
    """Enum class for all possible clean modes."""

    AUTO = "auto"
    SPOT_AREA = "spotArea"
    CUSTOM_AREA = "customArea"


class Clean(_ExecuteCommand):
    """Clean command."""

    name = "clean"

    def __init__(self, action: CleanAction) -> None:
        args = {"act": action.value}
        if action == CleanAction.START:
            args["type"] = CleanMode.AUTO.value
        super().__init__(args)


class CleanArea(Clean):
    """Clean area command."""

    def __init__(self, mode: CleanMode, area: str, cleanings: int = 1) -> None:
        super().__init__(CleanAction.START)
        if not isinstance(self.args, dict):
            raise ValueError("args must be a dict!")

        self.args["type"] = mode.value
        self.args["content"] = str(area)
        self.args["count"] = cleanings
