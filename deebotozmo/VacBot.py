from deebotozmo import *
from deebotozmo.commands import *
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.events import *
from deebotozmo.models import *

_LOGGER = logging.getLogger(__name__)


class VacBot:
    def __init__(
            self,
            auth: dict,
            vacuum: Vacuum,
            continent: str,

            country,
            live_map_enabled: bool=True,
            show_rooms_color: bool=False,
            verify_ssl=True,
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

        self._map: Optional[Map] = Map(show_rooms_color) if live_map_enabled else None

        self.errorEvents = EventEmitter()
        self.lifespanEvents = EventEmitter()
        self.fanspeedEvents = EventEmitter()
        self.cleanLogsEvents = EventEmitter()
        self.waterEvents = EventEmitter()
        self.batteryEvents = EventEmitter()
        self.statusEvents = EventEmitter()
        self.statsEvents = EventEmitter()
        self.roomEvents = EventEmitter()
        self.livemapEvents = EventEmitter()

    @property
    def map(self) -> Optional[Map]:
        return self._map

    def execute_command(self, command: Command):
        if command.name == CleanResume.name and self.vacuum_status != "STATE_PAUSED":
            command = CleanStart()

        response = self.json.send_command(command, self.vacuum)
        # self.handle(command.name, response)
        # todo only for debug return response
        return response

    # ---------------------------- REFRESH ROUTINES ----------------------------

    # todo add refresh map

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
        _LOGGER.debug("[refresh_cleanLogs] Begin")
        self.execute_command(GetCleanLogs())

    def refresh_all(self):
        self.refresh_statuses()
        self.refresh_stats()
        self.refresh_rooms()
        self.refresh_components()
        self.refresh_clean_logs()

    # ---------------------------- EVENT HANDLING ----------------------------

    def handle(self, event_name: str, event_data: dict):
        _LOGGER.debug(f"Handle {event_name} with {event_data}")
        event_name = event_name.lower()

        prefixes = [
            "on",  # incoming events (on)
            "off",  # incoming events for (3rd) unknown/unsaved map
            "report",  # incoming events (report)
            "get",  # remove from "get" commands
        ]

        for prefix in prefixes:
            if event_name.startswith(prefix):
                event_name = event_data[len(prefix):]

        # OZMO T8 series and newer
        if event_name.endswith("_V2".lower()):
            event_name = event_name[:-3]

        if event_name == "stats":
            self._handle_stats(event_data)
        elif event_name == "error":
            self._handle_error(event_data)
        elif event_name == "speed":
            self._handle_fan_speed(event_data)
        elif event_name.startswith("battery"):
            self._handle_battery(event_data)
        elif event_name == "chargestate":
            self._handle_charge_state(event_data)
        elif event_name == "lifespan":
            self._handle_life_span(event_data)
        elif event_name == "cleanlogs":
            self._handle_clean_logs(event_data)
        elif event_name == "cleaninfo":
            self._handle_clean_info(event_data)
        elif "map" in event_name or event_name == "pos":
            if self._map:
                self._map.handle(event_name, event_data)
            else:
                _LOGGER.debug(f"Map disabled. Ignoring event: {event_name}")
        else:
            _LOGGER.debug(f"Unknown event: {event_name} with {event_data}")

    def _handle_stats(self, event):
        code = event["body"]["code"]
        if code != 0:
            _LOGGER.error(f"Error in finding stats, status code={code}")  # Log this so we can identify more errors
            return

        data: dict = event["body"]["data"]

        stats_event = StatsEvent(
            data.get("area"),
            data.get("cid"),
            data.get("time"),
            data.get("type"),
            data.get("content")
        )

        self.statsEvents.notify(stats_event)

    def _handle_error(self, event):
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

    def _handle_fan_speed(self, event):
        response = event["body"]["data"]
        speed = FAN_SPEED_FROM_ECOVACS.get(response.get("speed"))

        if speed:
            self.fanspeedEvents.notify(FanSpeedEvent(speed))
        else:
            _LOGGER.warning(f"Could not process fan speed event with received data: {event}")

    def _handle_battery(self, event):
        response = event["body"]
        try:
            self.batteryEvents.notify(BatteryEvent(response["data"]["value"]))
        except ValueError:
            _LOGGER.warning("couldn't parse battery status " + response)

    def _handle_charge_state(self, event):
        response = event["body"]
        status = None

        if response["code"] == 0:
            if response["data"]["isCharging"] == 1:
                status = STATE_DOCKED
        else:
            if response["msg"] == "fail":
                if response["code"] == "30007":  # Already charging
                    status = STATE_DOCKED
                elif response["code"] == "5":  # Busy with another command
                    status = STATE_ERROR
                elif response["code"] == "3":  # Bot in stuck state, example dust bin out
                    status = STATE_ERROR

        if status:
            self.vacuum_status = status
            self.statusEvents.notify(StatusEvent(True, status))
        else:
            # todo should we set here STATE_ERROR?
            _LOGGER.error(f"Unknown charging status '{response.get('code')}'")

    def _handle_life_span(self, event):
        components = event["body"]["data"]

        component: dict
        for component in components:
            component_type = COMPONENT_FROM_ECOVACS.get(component.get("type"))
            left = component.get("left")
            total = component.get("total")

            if component_type and left and total:
                percent = (int(left) / int(total)) * 100
                self.lifespanEvents.notify(LifeSpanEvent(component_type, percent))
            else:
                _LOGGER.warning(f"Could not parse life span event with {event}")

    def _handle_water_info(self, event):
        response = event["body"]["data"]
        amount = response.get("amount")
        mop_attached = bool(response.get("enable"))

        if amount and mop_attached:
            self.waterEvents.notify(WaterInfoEvent(mop_attached, WATER_LEVEL_FROM_ECOVACS.get(amount)))
        else:
            _LOGGER.warning(f"Could not parse water info event with {event}")

    def _handle_clean_logs(self, event):
        response: Optional[List[dict]] = event.get("logs")

        # Ecovacs API is changing their API, this request may not working properly
        if response is not None and len(response) >= 0:
            logs: List[CleanLogEntry] = []
            for log in response:
                logs.append(CleanLogEntry(
                    timestamp= log.get("ts"),
                    imageUrl=log.get("imageUrl"),
                    type=log.get("type"),
                    area=log.get("area"),
                    stopReason=log.get("stopReason"),
                    totalTime=log.get("last")
                ))

            self.cleanLogsEvents.notify(CleanLogEvent(logs))
        else:
            _LOGGER.warning(f"Could not parse clean logs event with {event}")

    def _handle_clean_info(self, event):
        response = event.get("body", {}).get("data", {})
        status: Optional[str] = None
        if response.get("state") == "clean":
            if response.get("trigger") == "alert":
                status = "STATE_ERROR"
            elif response.get("trigger") in ["app","sched"]:
                motion_state = response.get("cleanState", {}).get("motionState")
                if motion_state == "working":
                    status = "STATE_CLEANING"
                elif motion_state == "pause":
                    status = "STATE_PAUSED"
                elif motion_state:
                    status = "STATE_RETURNING"

        if status:
            self.vacuum_status = status
            self.statusEvents.notify(StatusEvent(True, status))
        else:
            _LOGGER.warning(f"Could not parse clean info event with {event}")

        # Todo handle this calls
        # if STATE_CLEANING we should update stats and components, otherwise just the standard slow update
        # if self.vacuum_status == "STATE_CLEANING":
        #     self.refresh_stats()
        #     self.refresh_components()
        #
        # if self.vacuum_status == "STATE_DOCKED":
        #     self.refresh_cleanLogs()
