import asyncio
import logging
from typing import Union, Optional, List

import aiohttp

from deebotozmo.commands import *
from deebotozmo.constants import ERROR_CODES, FAN_SPEED_FROM_ECOVACS, COMPONENT_FROM_ECOVACS, WATER_LEVEL_FROM_ECOVACS
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.events import EventEmitter, ErrorEvent, PollingEventEmitter, LifeSpanEvent, FanSpeedEvent, \
    CleanLogEvent, WaterInfoEvent, BatteryEvent, StatusEvent, StatsEvent, CleanLogEntry
from deebotozmo.map import Map
from deebotozmo.models import *
from deebotozmo.util import get_PollingEventEmitter, get_EventEmitter

_LOGGER = logging.getLogger(__name__)


class VacuumBot:
    def __init__(
            self,
            session: aiohttp.ClientSession,
            auth: RequestAuth,
            vacuum: Vacuum,
            *,
            continent: str,
            country: str,
            verify_ssl: Union[bool, str] = True
    ):
        self._semaphore = asyncio.Semaphore(3)
        self._session = session
        self.vacuum: Vacuum = vacuum

        portal_url = EcovacsAPI.PORTAL_URL_FORMAT.format(continent=continent)

        if country.lower() == "cn":
            portal_url = EcovacsAPI.PORTAL_URL_FORMAT_CN

        self.json: EcovacsJSON = EcovacsJSON(
            session,
            auth,
            portal_url,
            verify_ssl
        )

        self.status: StatusEvent = StatusEvent(False, None)
        self.fw_version: Optional[str] = None

        self._map = Map(self.execute_command)

        self.statusEvents: EventEmitter[StatusEvent] = \
            get_EventEmitter(StatusEvent, [GetChargeState(), GetCleanInfo(self.vacuum)], self.execute_command)

        self.errorEvents: EventEmitter[ErrorEvent] = get_EventEmitter(ErrorEvent, [GetError()], self.execute_command)

        self.fanSpeedEvents: EventEmitter[FanSpeedEvent] = \
            get_EventEmitter(FanSpeedEvent, [GetFanSpeed()], self.execute_command)

        self.cleanLogsEvents: EventEmitter[CleanLogEvent] = \
            get_EventEmitter(CleanLogEvent, [GetCleanLogs()], self.execute_command)

        self.waterEvents: EventEmitter[WaterInfoEvent] = \
            get_EventEmitter(WaterInfoEvent, [GetWaterInfo()], self.execute_command)

        self.batteryEvents: EventEmitter[BatteryEvent] = \
            get_EventEmitter(BatteryEvent, [GetBattery()], self.execute_command)

        self.statsEvents: EventEmitter[StatsEvent] = \
            get_EventEmitter(StatsEvent, [GetStats()], self.execute_command)

        self.lifespanEvents: PollingEventEmitter[LifeSpanEvent] = \
            get_PollingEventEmitter(LifeSpanEvent, 60, [GetLifeSpan()], self.execute_command, self)

    @property
    def map(self) -> Map:
        return self._map

    async def execute_command(self, command: Command):
        if command.name == CleanResume.name and self.status.state != "STATE_PAUSED":
            command = CleanStart()

        async with self._semaphore:
            response = await self.json.send_command(command, self.vacuum)

        await self.handle(command.name, response)

    def set_available(self, available: bool):
        status = StatusEvent(available, self.status.state)
        self._set_status(status)

    def _set_state(self, state: VacuumState):
        self._set_status(StatusEvent(True, state))

    def _set_status(self, status: StatusEvent):
        _LOGGER.debug(f"Calling _set_status with {status}")

        last_status = self.status

        if self.status == status:
            _LOGGER.debug("Status still the same... Skipping")
            return

        self.status = status
        self.statusEvents.notify(status)

        if (not last_status.available) and status.available:
            # bot was unavailable
            self.statusEvents.request_refresh()
            self.errorEvents.request_refresh()
            self.fanSpeedEvents.request_refresh()
            self.cleanLogsEvents.request_refresh()
            self.waterEvents.request_refresh()
            self.batteryEvents.request_refresh()
            self.statsEvents.request_refresh()
            self.lifespanEvents.request_refresh()

    # ---------------------------- EVENT HANDLING ----------------------------

    async def handle(self, event_name: str, event: dict, requested: bool = True) -> None:
        """
        Handle the given event
        :param event_name: the name of the event or request
        :param event: the data of it
        :param requested: True if we manual requested the data (ex. via rest). MQTT -> False
        :return: None
        """

        _LOGGER.debug(f"Handle {event_name}: {event}")
        event_name = event_name.lower()

        prefixes = [
            "on",  # incoming events (on)
            "off",  # incoming events for (3rd) unknown/unsaved map
            "report",  # incoming events (report)
            "get",  # remove from "get" commands
        ]

        for prefix in prefixes:
            if event_name.startswith(prefix):
                event_name = event_name[len(prefix):]

        # OZMO T8 series and newer
        if event_name.endswith("_V2".lower()):
            event_name = event_name[:-3]

        if requested:
            if event.get("ret") == "ok":
                event = event.get("resp", {})
            else:
                _LOGGER.warning(f"Event {event_name} where ret != \"ok\": {event}")
                return

        event_body = event.get("body", {})
        event_header = event.get("header", {})

        if not (event_body and event_header):
            _LOGGER.warning(f"Invalid Event {event_name}: {event}")
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
            await self._handle_fan_speed(event_data)
        elif event_name.startswith("battery"):
            await self._handle_battery(event_data)
        elif event_name == "chargestate":
            if requested:
                await self._handle_charge_state_requested(event_body)
            else:
                await self._handle_charge_state(event_data)
        elif event_name == "lifespan":
            await self._handle_life_span(event_data)
        elif event_name == "cleanlogs":
            await self._handle_clean_logs(event)
        elif event_name == "cleaninfo":
            await self._handle_clean_info(event_data)
        elif event_name == "waterinfo":
            await self._handle_water_info(event_data)
        elif "map" in event_name or event_name == "pos":
            await self._map.handle(event_name, event_data, requested)
        elif event_name.startswith("set"):
            # ignore set commands for now
            pass
        elif event_name in ["playsound", "charge", "clean"]:
            # ignore this events
            pass
        else:
            _LOGGER.debug(f"Unknown event: {event_name} with {event}")

    async def _handle_stats(self, event_data: dict):
        stats_event = StatsEvent(
            event_data.get("area"),
            event_data.get("cid"),
            event_data.get("time"),
            event_data.get("type"),
            event_data.get("start")
        )

        self.statsEvents.notify(stats_event)

    async def _handle_error(self, event: dict, event_data: dict):
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
                _LOGGER.warning(f"Bot in error-state: code={error}, description={description}")
                self._set_state(VacuumState.STATE_ERROR)
            self.errorEvents.notify(ErrorEvent(error, description))
        else:
            _LOGGER.warning(f"Could not process error event with received data: {event}")

    async def _handle_fan_speed(self, event_data: dict):
        speed = FAN_SPEED_FROM_ECOVACS.get(event_data.get("speed"))

        if speed:
            self.fanSpeedEvents.notify(FanSpeedEvent(speed))
        else:
            _LOGGER.warning(f"Could not process fan speed event with received data: {event_data}")

    async def _handle_battery(self, event_data: dict):
        try:
            self.batteryEvents.notify(BatteryEvent(event_data["value"]))
        except ValueError:
            _LOGGER.warning(f"Couldn't parse battery status: {event_data}")

    async def _handle_charge_state_requested(self, event_body: dict):
        if event_body["code"] == 0:
            await self._handle_charge_state(event_body.get("data", {}))
        else:
            status: Optional[VacuumState] = None
            if event_body["msg"] == "fail":
                if event_body["code"] == "30007":  # Already charging
                    status = VacuumState.STATE_DOCKED
                elif event_body["code"] == "5":  # Busy with another command
                    status = VacuumState.STATE_ERROR
                elif event_body["code"] == "3":  # Bot in stuck state, example dust bin out
                    status = VacuumState.STATE_ERROR

            if status:
                self._set_state(status)

    async def _handle_charge_state(self, event_data: dict):
        if event_data.get("isCharging") == 1:
            self._set_state(VacuumState.STATE_DOCKED)

    async def _handle_life_span(self, event_data: dict):
        component: dict
        for component in event_data:
            component_type = COMPONENT_FROM_ECOVACS.get(component.get("type"))
            left = int(component.get("left", 0))
            total = int(component.get("total", 0))

            if component_type and total > 0:
                percent = round((left / total) * 100, 2)
                self.lifespanEvents.notify(LifeSpanEvent(component_type, percent))
            else:
                _LOGGER.warning(f"Could not parse life span event with {event_data}")

    async def _handle_water_info(self, event_data: dict):
        amount = event_data.get("amount")
        mop_attached = bool(event_data.get("enable"))

        if amount:
            self.waterEvents.notify(WaterInfoEvent(mop_attached, WATER_LEVEL_FROM_ECOVACS.get(amount)))
        else:
            _LOGGER.warning(f"Could not parse water info event with {event_data}")

    async def _handle_clean_logs(self, event):
        response: Optional[List[dict]] = event.get("logs")

        # Ecovacs API is changing their API, this request may not working properly
        if response is not None and len(response) >= 0:
            logs: List[CleanLogEntry] = []
            for log in response:
                logs.append(CleanLogEntry(
                    timestamp=log.get("ts"),
                    imageUrl=log.get("imageUrl"),
                    type=log.get("type"),
                    area=log.get("area"),
                    stopReason=log.get("stopReason"),
                    totalTime=log.get("last")
                ))

            self.cleanLogsEvents.notify(CleanLogEvent(logs))
        else:
            _LOGGER.warning(f"Could not parse clean logs event with {event}")

    async def _handle_clean_info(self, event_data: dict):
        status: Optional[VacuumState] = None
        if event_data.get("state") == "clean":
            if event_data.get("trigger") == "alert":
                status = VacuumState.STATE_ERROR
            else:
                motion_state = event_data.get("cleanState", {}).get("motionState")
                if motion_state == "working":
                    status = VacuumState.STATE_CLEANING
                elif motion_state == "pause":
                    status = VacuumState.STATE_PAUSED
                elif motion_state == "goCharging":
                    status = VacuumState.STATE_RETURNING

        elif event_data.get("state") == "goCharging":
            status = VacuumState.STATE_RETURNING

        if status:
            self._set_state(status)

        if self.status.state == VacuumState.STATE_DOCKED:
            self.cleanLogsEvents.request_refresh()
