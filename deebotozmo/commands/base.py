"""Base commands."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional, Type, Union

from deebotozmo.events import Events

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

    @classmethod
    @abstractmethod
    def _handle_body_data(cls, events: Events, data: Dict[str, Any]) -> bool:
        """Handle body data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        raise NotImplementedError

    @classmethod
    def _handle_body(cls, events: Events, data: Dict[str, Any]) -> bool:
        """Handle data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        data = data.get("data", data)
        return cls._handle_body_data(events, data)

    @classmethod
    def handle(cls, events: Events, data: Dict[str, Any]) -> bool:
        """Handle data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        data_body = data.get("body", data)
        return cls._handle_body(events, data_body)

    def handle_requested(self, events: Events, response: Dict[str, Any]) -> bool:
        """Handle response from a manual requested command.

        :return: True if data was valid and no error was included
        """
        if response.get("ret") == "ok":
            data = response.get("resp", response)
            return self.handle(events, data)

        _LOGGER.warning('Command "%s" was not successfully: %s', self.name, response)
        return False


class GetCommand(Command, ABC):
    """Base get command."""

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    def __init__(self) -> None:
        super().__init__()


class SetCommand(Command, ABC):
    """Base set command.

    Command needs to be linked to the "get" command, for handling (updating) the sensors.
    """

    # required as name is class variable, will be overwritten in subclasses
    name = "__invalid__"

    def __init__(
        self,
        args: Union[Dict, List, None] = None,
        remove_from_kwargs: Optional[List[str]] = None,
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
    def get_command(self) -> Type[Command]:
        """Return the corresponding "get" command."""
        raise NotImplementedError

    @classmethod
    def _handle_body(cls, events: Events, data: Dict[str, Any]) -> bool:
        """Handle data and notify the correct event subscriber.

        :return: True if data was valid and no error was included
        """
        # Success event looks like { "code": 0, "msg": "ok" }
        if data.get(_CODE, -1) == 0:
            return True

        _LOGGER.warning('Command "%s" was not successfully. data=%s', cls.name, data)
        return False

    @classmethod
    def _handle_body_data(cls, events: Events, data: Dict[str, Any]) -> bool:
        # not required as we overwrite "_handle_body"
        return True
