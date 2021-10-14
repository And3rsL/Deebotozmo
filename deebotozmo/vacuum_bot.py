"""Vacuum bot module."""
import asyncio
import inspect
import logging
import re
from typing import Any, Dict, Final, Optional, Union

import aiohttp

from deebotozmo.api_client import ApiClient
from deebotozmo.commands import (
    COMMANDS,
    Clean,
    Command,
    CommandWithHandling,
    GetBattery,
    GetChargeState,
    GetCleanInfo,
    GetCleanLogs,
    GetError,
    GetFanSpeed,
    GetLifeSpan,
    GetPos,
    GetStats,
    GetWaterInfo,
)
from deebotozmo.commands.clean import CleanAction
from deebotozmo.commands.custom import CustomCommand
from deebotozmo.commands.stats import GetTotalStats
from deebotozmo.event_emitter import (
    EventEmitter,
    PollingEventEmitter,
    RefreshOnStatusEventEmitter,
    StatusEventEmitter,
    VacuumEmitter,
)
from deebotozmo.events import (
    BatteryEvent,
    CleanLogEvent,
    CustomCommandEvent,
    ErrorEvent,
    FanSpeedEvent,
    LifeSpanEvent,
    StatsEvent,
    StatusEvent,
    TotalStatsEvent,
    WaterInfoEvent,
)
from deebotozmo.map import Map
from deebotozmo.models import DeviceInfo, VacuumState
from deebotozmo.util import get_refresh_function

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
        self._status: StatusEvent = StatusEvent(device_info.status == 1, None)

        self.fw_version: Optional[str] = None

        self.map: Final = Map(self.execute_command)

        status_ = StatusEventEmitter(
            get_refresh_function(
                [GetChargeState(), GetCleanInfo()],
                self.execute_command,
            )
        )
        self.events: Final = VacuumEmitter(
            battery=EventEmitter[BatteryEvent](
                get_refresh_function([GetBattery()], self.execute_command)
            ),
            clean_logs=RefreshOnStatusEventEmitter[CleanLogEvent](
                get_refresh_function([GetCleanLogs()], self.execute_command),
                status_,
                VacuumState.DOCKED,
            ),
            error=EventEmitter[ErrorEvent](
                get_refresh_function([GetError()], self.execute_command)
            ),
            fan_speed=EventEmitter[FanSpeedEvent](
                get_refresh_function([GetFanSpeed()], self.execute_command)
            ),
            lifespan=PollingEventEmitter[LifeSpanEvent](
                60, get_refresh_function([GetLifeSpan()], self.execute_command), status_
            ),
            map=self.map.events.map,
            rooms=self.map.events.rooms,
            stats=EventEmitter[StatsEvent](
                get_refresh_function([GetStats()], self.execute_command)
            ),
            status=status_,
            total_stats=RefreshOnStatusEventEmitter[TotalStatsEvent](
                get_refresh_function([GetTotalStats()], self.execute_command),
                status_,
                VacuumState.DOCKED,
            ),
            water_info=EventEmitter[WaterInfoEvent](
                get_refresh_function([GetWaterInfo()], self.execute_command)
            ),
            custom_command=EventEmitter[CustomCommandEvent](),
        )

        async def on_status(event: StatusEvent) -> None:
            last_status = self._status
            self._status = event
            if (not last_status.available) and event.available:
                # bot was unavailable
                for name, obj in inspect.getmembers(
                    self.events, lambda obj: isinstance(obj, EventEmitter)
                ):
                    if name != "status":
                        obj.request_refresh()

        self.events.status.subscribe(on_status)

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
        status = StatusEvent(available, self._status.state)
        self.events.status.notify(status)

    def _set_state(self, state: VacuumState) -> None:
        self.events.status.notify(StatusEvent(True, state))

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
