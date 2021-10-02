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
    def _handle_body_data(cls, events: Events, data: Dict[str, Any]) -> None:
        """Handle body data and notify the correct event subscriber."""
        raise NotImplementedError

    @classmethod
    def _handle_body(cls, events: Events, body: Dict[str, Any]) -> None:
        """Handle data and notify the correct event subscriber."""
        data = body.get("data", {})
        cls._handle_body_data(events, data)

    @classmethod
    def handle(cls, events: Events, data: Dict[str, Any]) -> None:
        """Handle data and notify the correct event subscriber."""
        data_body = data.get("body", {})
        cls._handle_body(events, data_body)

    def handle_requested(self, events: Events, response: Dict[str, Any]) -> None:
        """Handle response from a manual requested command."""
        if response.get("ret") == "ok":
            data = response.get("resp", response)
            self.handle(events, data)
        else:
            _LOGGER.warning(
                'Command "%s" was not successfully: %s', self.name, response
            )


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

    def _handle_body(  # type: ignore[override]
        self, events: Events, body: Dict[str, Any]
    ) -> None:
        """When set was successfully, handle command args with the "get" command."""
        # Success event looks like { "code": 0, "msg": "ok" }
        if _CODE not in body:
            # todo maybe throw a CommandException instead?
            raise ValueError(f'Expecting "code" to be in {body}')

        if body[_CODE] == 0 and isinstance(self.args, dict):
            self.get_command.handle(events, self.args)
