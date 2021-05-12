from .constants import *
from .ecovacs_api import EcovacsAPI
from .ecovacsjson import *
from .map import *

_LOGGER = logging.getLogger(__name__)


class VacBot:
    def __init__(
            self,
            user,
            resource,
            secret,
            vacuum,
            country,
            continent,
            live_map_enabled=True,
            show_rooms_color=False,
            verify_ssl=True,
    ):

        self.vacuum = vacuum

        self._failed_pings = 0
        self.is_available = False

        # These three are representations of the vacuum state as reported by the API
        self.battery_status = None

        # This is an aggregate state managed by the deebotozmo library, combining the clean and charge events to a single state
        self.vacuum_status = None
        self.fan_speed = None
        self.water_level = None
        self.mop_attached: bool = False

        self.fwversion = None
        self.modelVersion = self.vacuum["deviceName"]

        # Populated by component Lifespan reports
        self.components = {}

        # Map Components
        self.__map = Map()
        self.__map.draw_rooms = show_rooms_color

        self.live_map = None

        self.lastCleanLogs = []
        self.last_clean_image = None

        # Set none for clients to start
        self.json = None

        if country.lower() == "cn":
            self.json = EcoVacsJSON(
                user,
                resource,
                secret,
                continent,
                vacuum,
                EcovacsAPI.REALM,
                EcovacsAPI.PORTAL_URL_FORMAT_CN,
                verify_ssl=verify_ssl,
            )
        else:
            self.json = EcoVacsJSON(
                user,
                resource,
                secret,
                continent,
                vacuum,
                EcovacsAPI.REALM,
                EcovacsAPI.PORTAL_URL_FORMAT,
                verify_ssl=verify_ssl,
            )

        self.json.subscribe_to_ctls(self._handle_ctl)

        self.live_map_enabled = live_map_enabled

        # Stats
        self.stats_area = None
        self.stats_cid = None
        self.stats_time = None
        self.stats_type = None
        self.inuse_mapid = None

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

    ########### HANDLERS ###############
    def _handle_ctl(self, ctl):
        method = "_handle_" + ctl["event"]
        if hasattr(self, method):
            getattr(self, method)(ctl)

    def _handle_error(self, event):
        error = ""
        if "error" in event:
            error = event["error"]
        elif "errs" in event:
            error = event["errs"]

        if error != "":
            _LOGGER.warning("*** error = " + error)

        self.errorEvents.notify(event)

    def _handle_life_span(self, event):
        response = event["body"]["data"][0]
        type = response["type"]

        try:
            type = COMPONENT_FROM_ECOVACS[type]
        except KeyError:
            _LOGGER.warning("Unknown component type: '" + type + "'")

        left = int(response["left"])
        total = int(response["total"])

        lifespan = (left / total) * 100

        self.components[type] = lifespan

        self.lifespanEvents.notify(event)

    def _handle_fan_speed(self, event):
        response = event["body"]["data"]
        speed = response["speed"]

        try:
            speed = FAN_SPEED_FROM_ECOVACS[speed]
        except KeyError:
            _LOGGER.warning("Unknown fan speed: '" + str(speed) + "'")

        self.fan_speed = speed

        self.fanspeedEvents.notify(self.fan_speed)

    def _handle_clean_logs(self, event):
        response = event.get("logs")
        self.lastCleanLogs = []

        try:
            # Ecovacs API is changing their API, this request may not working properly
            if response is not None and len(response) >= 0:
                self.last_clean_image = response[0]["imageUrl"]
                for cleanLog in response:
                    self.lastCleanLogs.append(
                        {
                            "timestamp": cleanLog["ts"],
                            "imageUrl": cleanLog["imageUrl"],
                            "type": cleanLog["type"],
                        }
                    )

            self.cleanLogsEvents.notify(
                event=(self.lastCleanLogs, self.last_clean_image)
            )
        except:
            _LOGGER.warning("No last clean image found")

    def _handle_water_info(self, event):
        response = event["body"]["data"]
        amount = response["amount"]

        try:
            amount = WATER_LEVEL_FROM_ECOVACS[amount]
        except KeyError:
            _LOGGER.warning("Unknown water level: '" + str(amount) + "'")

        self.water_level = amount
        self.mop_attached = bool(response.get("enable"))

        self.waterEvents.notify(event=(self.water_level, self.mop_attached))

    def _handle_clean_report(self, event):
        self.fwversion = event["header"]["fwVer"]

        response = event["body"]["data"]
        if response["state"] == "clean":
            if response["trigger"] == "app" or response["trigger"] == "sched":
                if response["cleanState"]["motionState"] == "working":
                    self.vacuum_status = "STATE_CLEANING"
                elif response["cleanState"]["motionState"] == "pause":
                    self.vacuum_status = "STATE_PAUSED"
                else:
                    self.vacuum_status = "STATE_RETURNING"
            elif response["trigger"] == "alert":
                self.vacuum_status = "STATE_ERROR"

        self.is_available = True
        self.statusEvents.notify(self.vacuum_status)

        # if STATE_CLEANING we should update stats and components, otherwise just the standard slow update
        if self.vacuum_status == "STATE_CLEANING":
            self.refresh_stats()
            self.refresh_components()

        if self.vacuum_status == "STATE_DOCKED":
            self.refresh_cleanLogs()

    def _handle_map_trace(self, event):
        response = event["body"]["data"]
        totalCount = int(response["totalCount"])
        traceStart = int(response["traceStart"])
        pointCount = 200

        # No trace value avaiable
        if "traceValue" in response:
            if traceStart == 0:
                self.__map.traceValues = []

            # _LOGGER.debug(
            #    "Trace Request: TotalCount="
            #    + str(totalCount)
            #    + " traceStart="
            #    + str(traceStart)
            # )
            self.__map.updateTracePoints(response["traceValue"])

            if (traceStart + pointCount) < totalCount:
                self.exc_command(
                    "getMapTrace",
                    {"pointCount": pointCount, "traceStart": traceStart + pointCount},
                )

    def _handle_set_position(self, event):
        response = event["body"]["data"]

        # Charger
        if "chargePos" in response:
            charger_pos = response["chargePos"]
            self.__map.updateChargerPosition(charger_pos[0]["x"], charger_pos[0]["y"])

        if "deebotPos" in response:
            # Robot
            robot_pos = response["deebotPos"]
            self.__map.updateRobotPosition(robot_pos["x"], robot_pos["y"])

    def _handle_minor_map(self, event):
        response = event["body"]["data"]

        _LOGGER.debug("Handled minor_map : " + str(response["pieceIndex"]))

        self.__map.AddMapPiece(response["pieceIndex"], response["pieceValue"])

    def _handle_major_map(self, event):
        _LOGGER.debug("_handle_major_map begin")
        response = event["body"]["data"]

        values = response["value"].split(",")

        for i in range(64):
            if self.__map.isUpdatePiece(i, values[i]):
                _LOGGER.debug("MapPiece" + str(i) + " needs to be updated")
                self.exc_command(
                    "getMinorMap",
                    {"mid": response["mid"], "type": "ol", "pieceIndex": i},
                )

    def _handle_cached_map(self, event):
        response = event["body"]["data"]

        try:
            mapid = None
            for mapstatus in response["info"]:
                if mapstatus["using"] == 1:
                    mapid = mapstatus["mid"]

                    # IF MAP CHANGED WE SHOULD REFRESH ROOMS
                    if self.inuse_mapid != mapid:
                        self.inuse_mapid = mapid
                        self.refresh_rooms()

                    _LOGGER.debug("Using Map: " + str(mapid))

            self.__map.rooms = []
            self.exc_command("getMapSet", {"mid": mapid, "type": "ar"})
        except:
            _LOGGER.warning(
                "MapID not found -- did you finish your first auto cleaning?"
            )

    def _handle_map_set(self, event):
        response = event["body"]["data"]

        mid = response["mid"]
        msid = response["msid"]
        typemap = response["type"]

        for s in response["subsets"]:
            self.exc_command(
                "getMapSubSet",
                {"mid": mid, "msid": msid, "type": typemap, "mssid": s["mssid"]},
            )

    def _handle_map_sub_set(self, event):
        response = event["body"]["data"]
        subtype = int(response["subtype"])
        value = response["value"]

        self.__map.rooms.append(
            {
                "subtype": ROOMS_FROM_ECOVACS[subtype],
                "id": int(response["mssid"]),
                "values": value,
            }
        )

    def _handle_battery_info(self, event):
        response = event["body"]
        try:
            self.battery_status = response["data"]["value"]
        except ValueError:
            _LOGGER.warning("couldn't parse battery status " + response)

        self.batteryEvents.notify(self.battery_status)

    def _handle_charge_state(self, event):
        response = event["body"]
        status = "none"

        if response["code"] == 0:
            if response["data"]["isCharging"] == 1:
                status = "STATE_DOCKED"
        else:
            if (
                    response["msg"] == "fail" and response["code"] == "30007"
            ):  # Already charging
                status = "STATE_DOCKED"
            elif (
                    response["msg"] == "fail" and response["code"] == "5"
            ):  # Busy with another command
                status = "STATE_ERROR"
            elif (
                    response["msg"] == "fail" and response["code"] == "3"
            ):  # Bot in stuck state, example dust bin out
                status = "STATE_ERROR"
            else:
                _LOGGER.error(
                    "Unknown charging status '" + response["code"] + "'"
                )  # Log this so we can identify more errors

        if status != "none":
            self.vacuum_status = status
            self.is_available = True

        self.statusEvents.notify(self.vacuum_status)

    def _handle_stats(self, event):
        response = event["body"]

        if response["code"] == 0:
            if "area" in response["data"]:
                self.stats_area = response["data"]["area"]

            if "cid" in response["data"]:
                self.stats_cid = response["data"]["cid"]

            if "time" in response["data"]:
                self.stats_time = response["data"]["time"]

            if "type" in response["data"]:
                self.stats_type = response["data"]["type"]
        else:
            _LOGGER.error(
                "Error in finding stats, status code = " + response["code"]
            )  # Log this so we can identify more errors

        self.statsEvents.notify(event)

    ################################################################

    def _vacuum_address(self):
        return self.vacuum["did"]

    ############### REFRESH ROUTINES ###############################
    def refresh_components(self):
        _LOGGER.debug("[refresh_components] Begin")
        self.exc_command("getLifeSpan", [COMPONENT_TO_ECOVACS["brush"]])
        self.exc_command("getLifeSpan", [COMPONENT_TO_ECOVACS["sideBrush"]])
        self.exc_command("getLifeSpan", [COMPONENT_TO_ECOVACS["heap"]])

    def refresh_statuses(self):
        _LOGGER.debug("[refresh_statuses] Begin")

        if self.vacuum["class"] in ["bs40nz", "a1nNMoAGAsH", "vdehg6", "no61kx"]:
            self.exc_command("getCleanInfo_V2")
        else:
            self.exc_command("getCleanInfo")

        self.exc_command("getChargeState")
        self.exc_command("getBattery")
        self.exc_command("getSpeed")
        self.exc_command("getWaterInfo")

    def refresh_rooms(self):
        _LOGGER.debug("[refresh_rooms] Begin")
        self.exc_command("getCachedMapInfo")
        self.roomEvents.notify(None)

    def refresh_stats(self):
        _LOGGER.debug("[refresh_stats] Begin")
        self.exc_command("getStats")

    def refresh_cleanLogs(self):
        _LOGGER.debug("[refresh_cleanLogs] Begin")
        self.exc_command("GetCleanLogs")

    def refresh_liveMap(self, force=False):
        if self.vacuum_status == "STATE_CLEANING" or force == True:
            _LOGGER.debug("[refresh_liveMap] Begin")
            self.exc_command("getMapTrace", {"pointCount": 200, "traceStart": 0})
            self.exc_command("getPos", ["chargePos", "deebotPos"])
            self.exc_command("getMajorMap")
            self.live_map = self.__map.GetBase64Map()

            self.livemapEvents.notify(self.live_map)

    ###################################################################

    def setScheduleUpdates(
            self,
            status_cycle=10,
            components_cycle=60,
            stats_cycle=60,
            rooms_cycle=60,
            liveMap_cycle=5,
    ):

        self.updateEverythingNOW()

        self.json.schedule(status_cycle, self.refresh_statuses)
        self.json.schedule(stats_cycle, self.refresh_stats)
        self.json.schedule(rooms_cycle, self.refresh_rooms)
        self.json.schedule(components_cycle, self.refresh_components)

        if self.live_map_enabled:
            self.json.scheduleLiveMap(liveMap_cycle, self.refresh_liveMap)

    def disconnect(self):
        _LOGGER.debug("vacbot disconnected schedule")
        self.json.disconnect()

    def updateEverythingNOW(self):
        if self.live_map_enabled:
            self.refresh_liveMap(True)

        self.refresh_statuses()
        self.refresh_stats()
        self.refresh_rooms()
        self.refresh_components()
        self.refresh_cleanLogs()

    def getSavedRooms(self):
        return self.__map.rooms

    def getTypeRooms(self):
        return ROOMS_FROM_ECOVACS

    # Common ecovacs commands
    def Clean(self, type="auto"):
        _LOGGER.debug("[Command] Clean Start TYPE: " + type)
        self.exc_command("clean", {"act": CLEAN_ACTION_START, "type": type})
        self.refresh_statuses()

    def CleanPause(self):
        _LOGGER.debug("[Command] Clean Pause")
        self.exc_command("clean", {"act": CLEAN_ACTION_PAUSE})
        self.refresh_statuses()

    def CleanResume(self):
        if self.vacuum_status == "STATE_PAUSED":
            _LOGGER.debug("[Command] Clean Resume - Resume")
            self.exc_command("clean", {"act": CLEAN_ACTION_RESUME})
        else:
            _LOGGER.debug("[Command] Clean Resume - ActionStart")
            self.exc_command("clean", {"act": CLEAN_ACTION_START, "type": "auto"})

        self.refresh_statuses()

    def Charge(self):
        _LOGGER.debug("[Command] Charge")
        self.exc_command("charge", {"act": CHARGE_MODE_TO_ECOVACS["return"]})
        self.refresh_statuses()

    def PlaySound(self):
        _LOGGER.debug("[Command] PlaySound")
        self.exc_command("playSound", {"count": 1, "sid": 30})

    def Relocate(self):
        _LOGGER.debug("[Command] Relocate")
        self.exc_command("setRelocationState", {"mode": "manu"})

    def GetCleanLogs(self):
        _LOGGER.debug("[Command] GetCleanLogs")
        self.exc_command("GetCleanLogs")

    def CustomArea(self, map_position, cleanings=1):
        _LOGGER.debug(
            "[Command] CustomArea content="
            + str(map_position)
            + " count="
            + str(cleanings)
        )
        self.exc_command(
            "clean",
            {
                "act": "start",
                "content": str(map_position),
                "count": int(cleanings),
                "type": "customArea",
            },
        )
        self.refresh_statuses()

    def SpotArea(self, area, cleanings=1):
        _LOGGER.debug(
            "[Command] SpotArea content=" + str(area) + " count=" + str(cleanings)
        )
        self.exc_command(
            "clean",
            {
                "act": "start",
                "content": str(area),
                "count": int(cleanings),
                "type": "spotArea",
            },
        )
        self.refresh_statuses()

    def SetFanSpeed(self, speed=1):
        _LOGGER.debug("[Command] setSpeed speed=" + str(speed))
        self.exc_command("setSpeed", {"speed": FAN_SPEED_TO_ECOVACS[speed]})
        self.refresh_statuses()

    def SetWaterLevel(self, amount=1):
        _LOGGER.debug("[Command] setWaterInfo amount=" + str(amount))
        self.exc_command(
            "setWaterInfo", {"amount": WATER_LEVEL_TO_ECOVACS[amount], "enable": 0}
        )
        self.refresh_statuses()

    def exc_command(self, action, params=None):
        self.send_command(VacBotCommand(action, params))

    def send_command(self, action):
        self.json.send_command(action, self._vacuum_address())


class VacBotCommand:
    def __init__(self, name, args=None):
        if args is None:
            args = {}
        self.name = name
        self.args = args

    def __str__(self, *args, **kwargs):
        return self.command_name() + " command"

    def command_name(self):
        return self.__class__.__name__.lower()


class EventEmitter(object):
    """A very simple event emitting system."""

    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        listener = EventListener(self, callback)
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        self._subscribers.remove(listener)

    def notify(self, event):
        for subscriber in self._subscribers:
            subscriber.callback(event)


class EventListener(object):
    """Object that allows event consumers to easily unsubscribe from events."""

    def __init__(self, emitter, callback):
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        self._emitter.unsubscribe(self)
