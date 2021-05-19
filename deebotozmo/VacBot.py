import logging
from typing import Union

from deebotozmo.commands import *
from deebotozmo.constants import ERROR_CODES, FAN_SPEED_FROM_ECOVACS, STATE_DOCKED, STATE_ERROR, COMPONENT_FROM_ECOVACS, \
    WATER_LEVEL_FROM_ECOVACS
from deebotozmo.ecovacs_api import EcovacsAPI
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.events import *
from deebotozmo.map import Map
from deebotozmo.models import *

_LOGGER = logging.getLogger(__name__)


class VacBot:
    def __init__(
            self,
            auth: dict,
            vacuum: Vacuum,
            continent: str,
            country: str,
            *,
            live_map_enabled: bool = True,
            verify_ssl: Union[bool, str] = True
    ):
        self.vacuum: Vacuum = vacuum

        portal_url = EcovacsAPI.PORTAL_URL_FORMAT.format(continent=continent)

        if country.lower() == "cn":
            portal_url = EcovacsAPI.PORTAL_URL_FORMAT_CN.format(continent=continent)

        self.json: EcovacsJSON = EcovacsJSON(
            auth,
            portal_url,
            verify_ssl
        )

        self.vacuum_status = None

        self._map = Map(live_map_enabled, self.execute_command)

        self.errorEvents = EventEmitter()
        self.lifespanEvents = EventEmitter()
        self.fanspeedEvents = EventEmitter()
        self.cleanLogsEvents = EventEmitter()
        self.waterEvents = EventEmitter()
        self.batteryEvents = EventEmitter()
        self.statusEvents = EventEmitter()
        self.statsEvents = EventEmitter()

    @property
    def map(self) -> Map:
        return self._map

    def execute_command(self, command: Command):
        if command.name == CleanResume.name and self.vacuum_status != "STATE_PAUSED":
            command = CleanStart()

        response = self.json.send_command(command, self.vacuum)
        self.handle(command.name, response)

    # ---------------------------- REFRESH ROUTINES ----------------------------

    def refresh_map(self):
        _LOGGER.debug("[refresh_map] Begin")
        self.execute_command(GetMapTrace())
        self.execute_command(GetPos())
        self.execute_command(GetMajorMap())

    def refresh_components(self):
        _LOGGER.debug("[refresh_components] Begin")
        self.execute_command(GetLifeSpan())

    def refresh_statuses(self):
        _LOGGER.debug("[refresh_statuses] Begin")
        self.execute_command(GetCleanInfo(self.vacuum))
        self.execute_command(GetChargeState())
        self.execute_command(GetBattery())
        self.execute_command(GetFanSpeed())
        self.execute_command(GetWaterInfo())

    def refresh_rooms(self):
        _LOGGER.debug("[refresh_rooms] Begin")
        self.execute_command(GetCachedMapInfo())

    def refresh_stats(self):
        _LOGGER.debug("[refresh_stats] Begin")
        self.execute_command(GetStats())

    def refresh_clean_logs(self):
        _LOGGER.debug("[refresh_clean_logs] Begin")
        self.execute_command(GetCleanLogs())

    def refresh_all(self):
        self.refresh_statuses()
        self.refresh_stats()
        self.refresh_rooms()
        self.refresh_components()
        self.refresh_clean_logs()

    # ---------------------------- EVENT HANDLING ----------------------------

    def handle(self, event_name: str, event: dict):
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
            self._handle_error(event)
            return
        elif event.get("ret") == "ok":
            event_body = event.get("resp", {}).get("body", {})
            event_data = event_body.get("data", {})
        else:
            _LOGGER.warning(f"Event {event_name} where ret != \"ok\": {event}")
            return

        if event_name == "stats":
            self._handle_stats(event_body, event_data)
        elif event_name == "error":
            self._handle_error(event)
        elif event_name == "speed":
            self._handle_fan_speed(event_data)
        elif event_name.startswith("battery"):
            self._handle_battery(event_data)
        elif event_name == "chargestate":
            self._handle_charge_state(event_body)
        elif event_name == "lifespan":
            self._handle_life_span(event_data)
        elif event_name == "cleanlogs":
            self._handle_clean_logs(event)
        elif event_name == "cleaninfo":
            self._handle_clean_info(event_data)
        elif event_name == "waterinfo":
            self._handle_water_info(event_data)
        elif "map" in event_name or event_name == "pos":
            self._map.handle(event_name, event_data)
        elif event_name.startswith("set"):
            # ignore set commands for now
            pass
        elif event_name in ["playsound", "charge", "clean"]:
            # ignore this events
            pass
        else:
            _LOGGER.debug(f"Unknown event: {event_name} with {event}")

    def _handle_stats(self, event_body: dict, event_data: dict):
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

    def _handle_error(self, event: dict):
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

    def _handle_fan_speed(self, event_data: dict):
        speed = FAN_SPEED_FROM_ECOVACS.get(event_data.get("speed"))

        if speed:
            self.fanspeedEvents.notify(FanSpeedEvent(speed))
        else:
            _LOGGER.warning(f"Could not process fan speed event with received data: {event_data}")

    def _handle_battery(self, event_data: dict):
        try:
            self.batteryEvents.notify(BatteryEvent(event_data["value"]))
        except ValueError:
            _LOGGER.warning(f"couldn't parse battery status: {event_data}")

    def _handle_charge_state(self, event_body: dict):
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

    def _handle_life_span(self, event_data: dict):
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

    def _handle_water_info(self, event_data: dict):
        amount = event_data.get("amount")
        mop_attached = bool(event_data.get("enable"))

        if amount:
            self.waterEvents.notify(WaterInfoEvent(mop_attached, WATER_LEVEL_FROM_ECOVACS.get(amount)))
        else:
            _LOGGER.warning(f"Could not parse water info event with {event_data}")

    def _handle_clean_logs(self, event):
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

    def _handle_clean_info(self, event_data: dict):
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

        # Todo handle this calls
        # if STATE_CLEANING we should update stats and components, otherwise just the standard slow update
        # if self.vacuum_status == "STATE_CLEANING":
        #     self.refresh_stats()
        #     self.refresh_components()
        #
        # if self.vacuum_status == "STATE_DOCKED":
        #     self.refresh_cleanLogs()
