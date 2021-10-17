"""Vacuum bot module."""
import asyncio
import inspect
import logging
import re
from typing import Any, Dict, Final, Optional, Union

import aiohttp

from deebotozmo.api_client import ApiClient
from deebotozmo.commands import COMMANDS, Clean, Command, CommandWithHandling, GetPos
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

        self.events.subscribe(on_status)

        async def on_stats(_: StatsEventDto) -> None:
            self.events.request_refresh(LifeSpanEventDto)

        self.events.subscribe(on_stats)

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

        await self.handle(command, response)

    def set_available(self, available: bool) -> None:
        """Set available."""
        status = StatusEventDto(available, self._status.state)
        self.events.notify(status)

    def _set_state(self, state: VacuumState) -> None:
        self.events.notify(StatusEventDto(True, state))

    # ---------------------------- EVENT HANDLING ----------------------------

    async def handle(
        self, command: Union[str, Command, CustomCommand], message: Dict[str, Any]
    ) -> None:
        """Handle the given event.

        :param command: command object if manual request or command name
        :param message: the message (data) of it
        :return: None
        """

        if isinstance(command, (CommandWithHandling, CustomCommand)):
            _LOGGER.debug("Handle %s: %s", command.name, message)
            command.handle_requested(self.events, message)
        else:
            if isinstance(command, str):
                command_name = command
            else:
                command_name = command.name

            _LOGGER.debug("Handle %s: %s", command_name, message)
            fw_version = message.get("header", {}).get("fwVer", None)
            if fw_version:
                self.fw_version = fw_version

            # Handle command start start with "on","off","report" the same as "get" commands
            command_name = re.sub(
                _COMMAND_REPLACE_PATTERN,
                _COMMAND_REPLACE_REPLACEMENT,
                command_name,
            )

            # T8 series and newer
            if command_name.endswith("_V2"):
                command_name = command_name[:-3]

            found_command = COMMANDS.get(command_name, None)
            if found_command:
                found_command.handle(self.events, message)
            else:
                if command_name in COMMANDS.keys():
                    raise RuntimeError(
                        "Command support new format. Should never happen! Please contact developers."
                    )

                if "Map" in command_name or command_name == GetPos.name:
                    await self.map.handle(
                        command_name, message, not isinstance(command, str)
                    )
                else:
                    _LOGGER.debug('Unknown command "%s" with %s', command_name, message)
