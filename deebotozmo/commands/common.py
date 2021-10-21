"""Base commands."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Type, Union

from deebotozmo.command import Command
from deebotozmo.events.event_bus import EventBus
from deebotozmo.message import Message

_LOGGER = logging.getLogger(__name__)

_CODE = "code"


class CommandWithHandling(Command, Message, ABC):
    """Command, which handle response by itself."""

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    def handle_requested(self, event_bus: EventBus, response: Dict[str, Any]) -> bool:
        """Handle response from a manual requested command.

        :return: True if data was valid and no error was included
        """
        if response.get("ret") == "ok":
            data = response.get("resp", response)
            return self.handle(event_bus, data)

        _LOGGER.warning('Command "%s" was not successfully: %s', self.name, response)
        return False


class _NoArgsCommand(CommandWithHandling, ABC):
    """Command without args."""

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    def __init__(self) -> None:
        super().__init__()


class _ExecuteCommand(CommandWithHandling, ABC):
    """Command, which is executing something (ex. Charge)."""

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    @classmethod
    def _handle_body(cls, event_bus: EventBus, body: Dict[str, Any]) -> bool:
        """Handle message->body and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        # Success event looks like { "code": 0, "msg": "ok" }
        if body.get(_CODE, -1) == 0:
            return True

        _LOGGER.warning('Command "%s" was not successfully. body=%s', cls.name, body)
        return False


class SetCommand(_ExecuteCommand, ABC):
    """Base set command.

    Command needs to be linked to the "get" command, for handling (updating) the sensors.
    """

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    def __init__(
        self,
        args: Union[Dict, List, None],
        remove_from_kwargs: List[str],
        **kwargs: Mapping[str, Any],
    ) -> None:
        if remove_from_kwargs:
            for key in remove_from_kwargs:
                kwargs.pop(key, None)

        if kwargs:
            _LOGGER.debug("Following passed parameters will be ignored: %s", kwargs)

        super().__init__(args)

    @property
    @abstractmethod
    def get_command(self) -> Type[CommandWithHandling]:
        """Return the corresponding "get" command."""
        raise NotImplementedError
