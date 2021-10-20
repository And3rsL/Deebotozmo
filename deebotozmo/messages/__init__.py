"""Messages module."""


from typing import Dict, List, Type

from deebotozmo.commands import COMMANDS_WITH_HANDLING
from deebotozmo.message import Message
from deebotozmo.messages.stats import ReportStats

# fmt: off
# ordered by file asc
_MESSAGES: List[Type[Message]] = [
    ReportStats
]
# fmt: on

MESSAGES: Dict[str, Type[Message]] = {
    message.name: message
    for message in (
        _MESSAGES
        + [cmd for cmd in COMMANDS_WITH_HANDLING.values() if issubclass(cmd, Message)]
    )
}
