import logging
from typing import Union

import aiohttp

from deebotozmo.commands import *
from deebotozmo.constants import ERROR_CODES, FAN_SPEED_FROM_ECOVACS, STATE_DOCKED, STATE_ERROR, \
    COMPONENT_FROM_ECOVACS, WATER_LEVEL_FROM_ECOVACS
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.events import *
from deebotozmo.map import Map
from deebotozmo.models import *
from deebotozmo.util import get_PollingEventEmitter, get_EventEmitter

_LOGGER = logging.getLogger(__name__)


class VacuumBot:
    def __init__(
            self,
            session: aiohttp.ClientSession,
            auth: dict,
            vacuum: Vacuum,
            continent: str,
            country: str,
            *,
            live_map_enabled: bool = True,
            verify_ssl: Union[bool, str] = True
    ):
        self._session = session
        self.vacuum: Vacuum = vacuum

        portal_url = EcovacsAPI.PORTAL_URL_FORMAT.format(continent=continent)

        if country.lower() == "cn":
            portal_url = EcovacsAPI.PORTAL_URL_FORMAT_CN.format(continent=continent)

        self.json: EcovacsJSON = EcovacsJSON(
            session,
            auth,
            portal_url,
            verify_ssl
        )

        self.vacuum_status = None
        self.fw_version: Optional[str] = None

        self._map = Map(live_map_enabled, self.execute_command)

        self.errorEvents: EventEmitter[ErrorEvent] = EventEmitter[ErrorEvent]()

        self.lifespanEvents: PollingEventEmitter[LifeSpanEvent] = \
            get_PollingEventEmitter(LifeSpanEvent, 60, [GetLifeSpan()], self.execute_command)

        self.fanSpeedEvents: PollingEventEmitter[FanSpeedEvent] = \
            get_PollingEventEmitter(FanSpeedEvent, 10, [GetFanSpeed()], self.execute_command)

        self.cleanLogsEvents: EventEmitter[CleanLogEvent] = \
            get_EventEmitter(CleanLogEvent, [GetCleanLogs()], self.execute_command)

        self.waterEvents: PollingEventEmitter[WaterInfoEvent] = \
            get_PollingEventEmitter(WaterInfoEvent, 10, [GetWaterInfo()], self.execute_command)

        self.batteryEvents: PollingEventEmitter[BatteryEvent] = \
            get_PollingEventEmitter(BatteryEvent, 10, [GetBattery()], self.execute_command)

        self.statusEvents: EventEmitter[StatusEvent] = \
            get_PollingEventEmitter(StatusEvent, 10, [GetChargeState(), GetCleanInfo(self.vacuum)],
                                    self.execute_command)

        self.statsEvents: PollingEventEmitter[StatsEvent] = \
            get_PollingEventEmitter(StatsEvent, 60, [GetStats()], self.execute_command)

    @property
    def map(self) -> Map:
        return self._map

    async def execute_command(self, command: Command):
        if command.name == CleanResume.name and self.vacuum_status != "STATE_PAUSED":
            command = CleanStart()

        response = await self.json.send_command(command, self.vacuum)
        await self.handle(command.name, response)

    # ---------------------------- EVENT HANDLING ----------------------------

    async def handle(self, event_name: str, event: dict):
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

        if event_name == "error":
            await self._handle_error(event)
            return
        elif event.get("ret") == "ok":
            event_body = event.get("resp", {}).get("body", {})
            event_header = event.get("resp", {}).get("header", {})
            event_data = event_body.get("data", {})
        else:
            _LOGGER.warning(f"Event {event_name} where ret != \"ok\": {event}")
            return

        fw_version = event_header.get("fwVer")
        if fw_version:
            self.fw_version = fw_version

        if event_name == "stats":
            await self._handle_stats(event_body, event_data)
        elif event_name == "error":
            await self._handle_error(event)
        elif event_name == "speed":
            await self._handle_fan_speed(event_data)
        elif event_name.startswith("battery"):
            await self._handle_battery(event_data)
        elif event_name == "chargestate":
            await self._handle_charge_state(event_body)
        elif event_name == "lifespan":
            await self._handle_life_span(event_data)
        elif event_name == "cleanlogs":
            await self._handle_clean_logs(event)
        elif event_name == "cleaninfo":
            await self._handle_clean_info(event_data)
        elif event_name == "waterinfo":
            await self._handle_water_info(event_data)
        elif "map" in event_name or event_name == "pos":
            await self._map.handle(event_name, event_data)
        elif event_name.startswith("set"):
            # ignore set commands for now
            pass
        elif event_name in ["playsound", "charge", "clean"]:
            # ignore this events
            pass
        else:
            _LOGGER.debug(f"Unknown event: {event_name} with {event}")

    async def _handle_stats(self, event_body: dict, event_data: dict):
        code = event_body.get("code")
        if code != 0:
            _LOGGER.error(f"Error in finding stats, status code={code}")  # Log this so we can identify more errors
            return

        stats_event = StatsEvent(
            event_data.get("area"),
            event_data.get("cid"),
            event_data.get("time"),
            event_data.get("type"),
            event_data.get("start")
        )

        self.statsEvents.notify(stats_event)

    async def _handle_error(self, event: dict):
        error = None
        if "error" in event:
            error = event["error"]
        elif "errs" in event:
            error = event["errs"]

        if error:
            _LOGGER.warning("*** error = " + error)
            self.errorEvents.notify(ErrorEvent(error, ERROR_CODES.get(error)))
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
            _LOGGER.warning(f"couldn't parse battery status: {event_data}")

    async def _handle_charge_state(self, event_body: dict):
        status = None

        if event_body["code"] == 0:
            if event_body["data"]["isCharging"] == 1:
                status = STATE_DOCKED
        else:
            if event_body["msg"] == "fail":
                if event_body["code"] == "30007":  # Already charging
                    status = STATE_DOCKED
                elif event_body["code"] == "5":  # Busy with another command
                    status = STATE_ERROR
                elif event_body["code"] == "3":  # Bot in stuck state, example dust bin out
                    status = STATE_ERROR

        if status:
            self.vacuum_status = status
            self.statusEvents.notify(StatusEvent(True, status))

    async def _handle_life_span(self, event_data: dict):
        component: dict
        for component in event_data:
            component_type = COMPONENT_FROM_ECOVACS.get(component.get("type"))
            left = component.get("left")
            total = component.get("total")

            if component_type and left and total:
                percent = (int(left) / int(total)) * 100
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
        status: Optional[str] = None
        if event_data.get("state") == "clean":
            if event_data.get("trigger") == "alert":
                status = "STATE_ERROR"
            elif event_data.get("trigger") in ["app", "sched"]:
                motion_state = event_data.get("cleanState", {}).get("motionState")
                if motion_state == "working":
                    status = "STATE_CLEANING"
                elif motion_state == "pause":
                    status = "STATE_PAUSED"
                elif motion_state:
                    status = "STATE_RETURNING"

        if status:
            self.vacuum_status = status
            self.statusEvents.notify(StatusEvent(True, status))

        # if STATE_CLEANING we should update stats and components, otherwise just the standard slow update
        if self.vacuum_status == "STATE_CLEANING":
            tasks = [
                asyncio.create_task(self.statsEvents.refresh()),
                asyncio.create_task(self.lifespanEvents.refresh())
            ]
            await asyncio.gather(*tasks)

        elif self.vacuum_status == "STATE_DOCKED":
            await self.cleanLogsEvents.refresh()
