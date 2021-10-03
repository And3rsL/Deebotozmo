"""Vacuum bot module."""
import asyncio
import logging
import re
from typing import Any, Dict, Final, List, Optional, Union

import aiohttp

from deebotozmo.commands import COMMANDS, Command, GetWaterInfo
from deebotozmo.commands.fan_speed import GetFanSpeed
from deebotozmo.commands_old import CleanResume, CleanStart
from deebotozmo.commands_old import Command as OldCommand
from deebotozmo.commands_old import (
    GetBattery,
    GetChargeState,
    GetCleanInfo,
    GetCleanLogs,
    GetError,
    GetLifeSpan,
    GetStats,
)
from deebotozmo.constants import COMPONENT_FROM_ECOVACS, ERROR_CODES
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.event_emitter import EventEmitter, PollingEventEmitter, VacuumEmitter
from deebotozmo.events import (
    BatteryEvent,
    CleanLogEntry,
    CleanLogEvent,
    ErrorEvent,
    FanSpeedEvent,
    StatsEvent,
    StatusEvent,
    WaterInfoEvent,
)
from deebotozmo.map import Map
from deebotozmo.models import RequestAuth, Vacuum, VacuumState
from deebotozmo.util import get_refresh_function

_LOGGER = logging.getLogger(__name__)

_COMMAND_REPLACE_PATTERN = "^((on)|(off)|(report))"
_COMMAND_REPLACE_REPLACEMENT = "get"


class VacuumBot:
    """Vacuum bot representation."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: RequestAuth,
        vacuum: Vacuum,
        *,
        continent: str,
        country: str,
        verify_ssl: Union[bool, str] = True,
    ):
        self._semaphore = asyncio.Semaphore(3)
        self._session = session
        self.vacuum: Vacuum = vacuum

        portal_url = EcovacsAPI.PORTAL_URL_FORMAT.format(continent=continent)

        if country.lower() == "cn":
            portal_url = EcovacsAPI.PORTAL_URL_FORMAT_CN

        self.json: EcovacsJSON = EcovacsJSON(session, auth, portal_url, verify_ssl)

        self._status: StatusEvent = StatusEvent(False, None)
        self.fw_version: Optional[str] = None

        self.map: Final = Map(self.execute_command)

        status_ = EventEmitter[StatusEvent](
            get_refresh_function(
                [GetChargeState(), GetCleanInfo(self.vacuum)],
                self.execute_command,
            )
        )
        self.events: Final = VacuumEmitter(
            battery=EventEmitter[BatteryEvent](
                get_refresh_function([GetBattery()], self.execute_command)
            ),
            clean_logs=EventEmitter[CleanLogEvent](
                get_refresh_function([GetCleanLogs()], self.execute_command)
            ),
            error=EventEmitter[ErrorEvent](
                get_refresh_function([GetError()], self.execute_command)
            ),
            fan_speed=EventEmitter[FanSpeedEvent](
                get_refresh_function([GetFanSpeed()], self.execute_command)
            ),
            lifespan=PollingEventEmitter[Dict[str, float]](
                60, get_refresh_function([GetLifeSpan()], self.execute_command), status_
            ),
            map=self.map.events.map,
            rooms=self.map.events.rooms,
            stats=EventEmitter[StatsEvent](
                get_refresh_function([GetStats()], self.execute_command)
            ),
            status=status_,
            water_info=EventEmitter[WaterInfoEvent](
                get_refresh_function([GetWaterInfo()], self.execute_command)
            ),
        )

    async def execute_command(self, command: Union[Command, OldCommand]) -> None:
        """Execute given command and handle response."""
        if (
            command.name == CleanResume().name
            and self._status.state != VacuumState.STATE_PAUSED
        ):
            command = CleanStart()
        elif (
            command.name == CleanStart().name
            and self._status.state == VacuumState.STATE_PAUSED
        ):
            command = CleanResume()

        async with self._semaphore:
            response = await self.json.send_command(command, self.vacuum)

        await self.handle(command.name, response, command)

    def set_available(self, available: bool) -> None:
        """Set available."""
        status = StatusEvent(available, self._status.state)
        self._set_status(status)

    def _set_state(self, state: VacuumState) -> None:
        self._set_status(StatusEvent(True, state))

    def _set_status(self, status: StatusEvent) -> None:
        _LOGGER.debug("Calling _set_status with %s", status)

        last_status = self._status

        if self._status == status:
            _LOGGER.debug("Status still the same... Skipping")
            return

        self._status = status
        self.events.status.notify(status)

        if (not last_status.available) and status.available:
            # bot was unavailable
            for event in dir(self.events):
                if isinstance(event, EventEmitter):
                    event.request_refresh()

    # ---------------------------- EVENT HANDLING ----------------------------

    async def handle(
        self,
        command_name: str,
        data: Dict[str, Any],
        requested_command: Optional[Union[Command, OldCommand]],
    ) -> None:
        """Handle the given event.

        :param command_name: the name of the event or request
        :param data: the data of it
        :param requested_command: The request command object. None -> MQTT
        :return: None
        """
        if requested_command and isinstance(requested_command, Command):
            requested_command.handle_requested(self.events, data)
        else:
            # Handle command start start with "on","off","report" the same as "get" commands
            command_name = re.sub(
                _COMMAND_REPLACE_PATTERN, _COMMAND_REPLACE_REPLACEMENT, command_name
            )

            command = COMMANDS.get(command_name, None)
            if command:
                command.handle(self.events, data)
            else:
                await self._handle_old(
                    command_name, data, requested_command is not None
                )

    async def _handle_old(
        self, event_name: str, event: dict, requested: bool = True
    ) -> None:
        # pylint: disable=too-many-branches

        _LOGGER.debug("Handle %s: %s", event_name, event)
        event_name = event_name.lower()

        prefixes = [
            "on",  # incoming events (on)
            "off",  # incoming events for (3rd) unknown/unsaved map
            "report",  # incoming events (report)
            "get",  # remove from "get" commands
        ]

        for prefix in prefixes:
            if event_name.startswith(prefix):
                event_name = event_name[len(prefix) :]

        # OZMO T8 series and newer
        if event_name.endswith("_V2".lower()):
            event_name = event_name[:-3]

        if requested:
            if event.get("ret") == "ok":
                if event_name == "cleanlogs":
                    await self._handle_clean_logs(event)
                    return

                event = event.get("resp", event)
            else:
                _LOGGER.warning('Event %s where ret != "ok": %s', event_name, event)
                return

        event_body = event.get("body", {})
        event_header = event.get("header", {})

        if not (event_body and event_header):
            _LOGGER.warning("Invalid Event %s: %s", event_name, event)
            return

        event_data = event_body.get("data", {})

        fw_version = event_header.get("fwVer")
        if fw_version:
            self.fw_version = fw_version

        if event_name == "stats":
            await self._handle_stats(event_data)
        elif event_name == "error":
            await self._handle_error(event, event_data)
        elif event_name == "speed":
            raise NotImplementedError()
        elif event_name.startswith("battery"):
            await self._handle_battery(event_data)
        elif event_name == "chargestate":
            if requested:
                await self._handle_charge_state_requested(event_body)
            else:
                await self._handle_charge_state(event_data)
        elif event_name == "lifespan":
            await self._handle_life_span(event_data)
        elif event_name == "cleaninfo":
            await self._handle_clean_info(event_data)
        elif event_name == "waterinfo":
            raise NotImplementedError()
        elif "map" in event_name or event_name == "pos":
            await self.map.handle(event_name, event_data, requested)
        elif event_name.startswith("set"):
            # ignore set commands for now
            pass
        elif event_name in ["playsound", "charge", "clean"]:
            # ignore this events
            pass
        else:
            _LOGGER.debug("Unknown event: %s with %s", event_name, event)

    async def _handle_stats(self, event_data: dict) -> None:
        stats_event = StatsEvent(
            event_data.get("area"),
            event_data.get("cid"),
            event_data.get("time"),
            event_data.get("type"),
            event_data.get("start"),
        )

        self.events.stats.notify(stats_event)

    async def _handle_error(self, event: dict, event_data: dict) -> None:
        error: Optional[int] = None
        if "error" in event:
            error = event["error"]
        elif "errs" in event:
            error = event["errs"]
        elif "code" in event_data:
            codes = event_data.get("code", [])
            if codes:
                # the last error code
                error = codes[-1]

        if error is not None:
            description = ERROR_CODES.get(error)
            if error != 0:
                _LOGGER.warning(
                    "Bot in error-state: code=%d, description=%s", error, description
                )
                self._set_state(VacuumState.STATE_ERROR)
            self.events.error.notify(ErrorEvent(error, description))
        else:
            _LOGGER.warning(
                "Could not process error event with received data: %s", event
            )

    async def _handle_battery(self, event_data: dict) -> None:
        try:
            self.events.battery.notify(BatteryEvent(event_data["value"]))
        except ValueError:
            _LOGGER.warning("Couldn't parse battery status: %s", event_data)

    async def _handle_charge_state_requested(self, event_body: dict) -> None:
        if event_body["code"] == 0:
            await self._handle_charge_state(event_body.get("data", {}))
        else:
            status: Optional[VacuumState] = None
            if event_body["msg"] == "fail":
                if event_body["code"] == "30007":  # Already charging
                    status = VacuumState.STATE_DOCKED
                elif event_body["code"] == "5":  # Busy with another command
                    status = VacuumState.STATE_ERROR
                elif (
                    event_body["code"] == "3"
                ):  # Bot in stuck state, example dust bin out
                    status = VacuumState.STATE_ERROR

            if status:
                self._set_state(status)

    async def _handle_charge_state(self, event_data: dict) -> None:
        if event_data.get("isCharging") == 1:
            self._set_state(VacuumState.STATE_DOCKED)

    async def _handle_life_span(
        self, event_data: List[Dict[str, Union[str, int]]]
    ) -> None:
        components: Dict[str, float] = {}
        for component in event_data:
            component_type = COMPONENT_FROM_ECOVACS.get(str(component.get("type")))
            left = int(component.get("left", 0))
            total = int(component.get("total", 0))

            if component_type and total > 0:
                percent = round((left / total) * 100, 2)
                components[component_type] = percent
            else:
                _LOGGER.warning("Could not parse life span event with %s", event_data)

        self.events.lifespan.notify(components)

    async def _handle_clean_logs(self, event: Dict) -> None:
        response: Optional[List[dict]] = event.get("logs")

        # Ecovacs API is changing their API, this request may not working properly
        if response is not None and len(response) >= 0:
            logs: List[CleanLogEntry] = []
            for log in response:
                logs.append(
                    CleanLogEntry(
                        timestamp=log.get("ts"),
                        image_url=log.get("imageUrl"),
                        type=log.get("type"),
                        area=log.get("area"),
                        stop_reason=log.get("stopReason"),
                        total_time=log.get("last"),
                    )
                )

            self.events.clean_logs.notify(CleanLogEvent(logs))
        else:
            _LOGGER.warning("Could not parse clean logs event with %s", event)

    async def _handle_clean_info(self, event_data: dict) -> None:
        status: Optional[VacuumState] = None
        if event_data.get("trigger") == "alert":
            status = VacuumState.STATE_ERROR
        elif event_data.get("state") == "clean":
            clean_state = event_data.get("cleanState", {})
            motion_state = clean_state.get("motionState")
            if motion_state == "working":
                status = VacuumState.STATE_CLEANING
            elif motion_state == "pause":
                status = VacuumState.STATE_PAUSED
            elif motion_state == "goCharging":
                status = VacuumState.STATE_RETURNING

            clean_type = clean_state.get("type")
            content = clean_state.get("content", {})
            if "type" in content:
                clean_type = content.get("type")

            if clean_type == "customArea":
                area_values = content
                if "value" in content:
                    area_values = content.get("value")

                _LOGGER.debug("Last custom area values (x1,y1,x2,y2): %s", area_values)

        elif event_data.get("state") == "goCharging":
            status = VacuumState.STATE_RETURNING

        if status:
            self._set_state(status)

        if self._status.state == VacuumState.STATE_DOCKED:
            self.events.clean_logs.request_refresh()
