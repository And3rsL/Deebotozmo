"""Base commands."""
import logging
from abc import ABC, abstractmethod
from enum import IntEnum, unique
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union

from deebotozmo.event_emitter import VacuumEmitter

_LOGGER = logging.getLogger(__name__)

_CODE = "code"


class Command(ABC):
    """Abstract command object."""

    def __init__(self, args: Union[Dict, List, None] = None) -> None:
        if args is None:
            args = {}
        self._args = args

    @classmethod
    @property
    @abstractmethod
    def name(cls) -> str:
        """Command name."""
        raise NotImplementedError

    @property
    def args(self) -> Union[Dict[str, Any], List]:
        """Command additional arguments."""
        return self._args


class CommandWithHandling(Command, ABC):
    """Command, which handle response by itself."""

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    @classmethod
    def _handle_body_data_list(cls, events: VacuumEmitter, data: List) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        raise NotImplementedError

    @classmethod
    def _handle_body_data_dict(
        cls, events: VacuumEmitter, data: Dict[str, Any]
    ) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        raise NotImplementedError

    @classmethod
    def _handle_body_data(
        cls, events: VacuumEmitter, data: Union[Dict[str, Any], List]
    ) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        if isinstance(data, dict):
            return cls._handle_body_data_dict(events, data)

        if isinstance(data, list):
            return cls._handle_body_data_list(events, data)

    @classmethod
    def _handle_body(cls, events: VacuumEmitter, body: Dict[str, Any]) -> bool:
        """Handle message->body and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        data = body.get("data", body)
        return cls._handle_body_data(events, data)

    @classmethod
    def handle(cls, events: VacuumEmitter, message: Dict[str, Any]) -> bool:
        """Handle message and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        data_body = message.get("body", message)
        return cls._handle_body(events, data_body)

    def handle_requested(self, events: VacuumEmitter, response: Dict[str, Any]) -> bool:
        """Handle response from a manual requested command.

        :return: True if data was valid and no error was included
        """
        if response.get("ret") == "ok":
            data = response.get("resp", response)
            return self.handle(events, data)

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
    def _handle_body(cls, events: VacuumEmitter, body: Dict[str, Any]) -> bool:
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


@unique
class DisplayNameIntEnum(IntEnum):
    """Int enum with a property "display_name"."""

    def __new__(cls, *args: Tuple, **_: Mapping) -> "DisplayNameIntEnum":
        """Create new enum."""
        obj = int.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _: int, display_name: Optional[str] = None):
        super().__init__()
        self._display_name = display_name

    @property
    def display_name(self) -> str:
        """Return the custom display name or the lowered name property."""
        if self._display_name:
            return self._display_name

        return self.name.lower()

    @classmethod
    def get(cls, value: str) -> "DisplayNameIntEnum":
        """Get enum member from name or display_name."""
        value = str(value).upper()
        if value in cls.__members__:
            return cls[value]

        for member in cls:
            if value == member.display_name.upper():
                return member

        raise ValueError(f"'{value}' is not a valid {cls.__name__} member")
