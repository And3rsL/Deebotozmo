"""Vacuum bot module."""
import asyncio
import inspect
import logging
import re
from typing import Any, Dict, Final, Optional, Union

import aiohttp

from deebotozmo.api_client import ApiClient
from deebotozmo.command import Command
from deebotozmo.commands import Clean, CommandWithHandling, GetPos
from deebotozmo.commands.clean import CleanAction
from deebotozmo.commands.custom import CustomCommand
from deebotozmo.events import (
    CleanLogEventDto,
    LifeSpanEventDto,
    StatsEventDto,
    StatusEventDto,
    TotalStatsEventDto,
)
from deebotozmo.events.event_bus import EventBus
from deebotozmo.map import Map
from deebotozmo.messages import MESSAGES
from deebotozmo.models import DeviceInfo, VacuumState

_LOGGER = logging.getLogger(__name__)

_COMMAND_REPLACE_PATTERN = "^((on)|(off)|(report))"
_COMMAND_REPLACE_REPLACEMENT = "get"


class VacuumBot:
    """Vacuum bot representation."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        device_info: DeviceInfo,
        api_client: ApiClient,
    ):
        self._session = session
        self.device_info: Final[DeviceInfo] = device_info
        self._api_client = api_client

        self._semaphore = asyncio.Semaphore(3)
        self._status: StatusEventDto = StatusEventDto(device_info.status == 1, None)

        self.fw_version: Optional[str] = None
        self.events: Final[EventBus] = EventBus(self.execute_command)

        self.map: Final[Map] = Map(self.execute_command, self.events)

        async def on_status(event: StatusEventDto) -> None:
            last_status = self._status
            self._status = event
            if (not last_status.available) and event.available:
                # bot was unavailable
                for name, obj in inspect.getmembers(
                    self.events, lambda obj: isinstance(obj, EventBus)
                ):
                    if name != "status":
                        obj.request_refresh()
            elif event.state == VacuumState.DOCKED:
                self.events.request_refresh(CleanLogEventDto)
                self.events.request_refresh(TotalStatsEventDto)

        self.events.subscribe(StatusEventDto, on_status)

        async def on_stats(_: StatsEventDto) -> None:
            self.events.request_refresh(LifeSpanEventDto)

        self.events.subscribe(StatsEventDto, on_stats)

    async def execute_command(self, command: Union[Command, CustomCommand]) -> None:
        """Execute given command and handle response."""
        if (
            command == Clean(CleanAction.RESUME)
            and self._status.state != VacuumState.PAUSED
        ):
            command = Clean(CleanAction.START)
        elif (
            command == Clean(CleanAction.START)
            and self._status.state == VacuumState.PAUSED
        ):
            command = Clean(CleanAction.RESUME)

        async with self._semaphore:
            response = await self._api_client.send_command(command, self.device_info)

        _LOGGER.debug("Handle command %s: %s", command.name, response)
        if isinstance(command, (CommandWithHandling, CustomCommand)):
            command.handle_requested(self.events, response)
            if isinstance(command, CustomCommand):
                # Responses of CustomCommands will be handled like messages got via mqtt,
                # so build in events will be raised if this response too.
                await self.handle_message(command.name, response)
        elif "Map" in command.name or command.name == GetPos.name:
            # todo refactor map commands and remove it # pylint: disable=fixme
            await self.map._handle(  # pylint: disable=protected-access
                command.name, response, True
            )
        else:
            _LOGGER.warning("Unsupported command! Command %s", command.name)

    def set_available(self, available: bool) -> None:
        """Set available."""
        status = StatusEventDto(available, self._status.state)
        self.events.notify(status)

    async def handle_message(
        self, message_name: str, message_data: Dict[str, Any]
    ) -> None:
        """Handle the given message.

        :param message_name: message name
        :param message_data: message data
        :return: None
        """
        _LOGGER.debug("Handle message %s: %s", message_name, message_data)
        fw_version = message_data.get("header", {}).get("fwVer", None)
        if fw_version:
            self.fw_version = fw_version

        message_type = MESSAGES.get(message_name, None)
        if message_type:
            message_type.handle(self.events, message_data)
            return

        _LOGGER.debug("Falling back to old handling way...")
        # Handle message starting with "on","off","report" the same as "get" commands
        message_name = re.sub(
            _COMMAND_REPLACE_PATTERN,
            _COMMAND_REPLACE_REPLACEMENT,
            message_name,
        )

        # T8 series and newer
        if message_name.endswith("_V2"):
            message_name = message_name[:-3]

        found_command = MESSAGES.get(message_name, None)
        if found_command:
            found_command.handle(self.events, message_data)
        elif "Map" in message_name or message_name == GetPos.name:
            await self.map._handle(  # pylint: disable=protected-access
                message_name, message_data, False
            )
        else:
            _LOGGER.debug('Unknown message "%s" with %s', message_name, message_data)
