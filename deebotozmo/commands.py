from deebotozmo.constants import FAN_SPEED_TO_ECOVACS, WATER_LEVEL_TO_ECOVACS, CLEAN_ACTION_START, CLEAN_ACTION_PAUSE, \
    CLEAN_ACTION_RESUME, COMPONENT_MAIN_BRUSH, \
    COMPONENT_SIDE_BRUSH, COMPONENT_FILTER, MAP_TRACE_POINT_COUNT, CLEAN_ACTION_STOP
from deebotozmo.models import Vacuum


class Command:

    def __init__(self, name: str, args=None):
        if args is None:
            args = {}
        self._name: str = name
        self._args: dict = args

    @property
    def name(self) -> str:
        return self._name

    @property
    def args(self) -> dict:
        return self._args


class SetFanSpeed(Command):

    def __init__(self, speed: str):
        super().__init__("setSpeed", {
            "speed": FAN_SPEED_TO_ECOVACS.get(speed, 0)
        })


class SetWaterLevel(Command):

    def __init__(self, amount: str):
        super().__init__("setWaterInfo", {
            "amount": WATER_LEVEL_TO_ECOVACS.get(amount, 2),
            "enable": 0
        })


class Relocate(Command):

    def __init__(self):
        super().__init__("setRelocationState", {
            "mode": "manu"
        })


class PlaySound(Command):

    def __init__(self):
        super().__init__("playSound", {
            "count": 1,
            "sid": 30
        })


class Charge(Command):

    def __init__(self):
        super().__init__("charge", {
            "act": "go"
        })


class CleanStart(Command):

    def __init__(self, clean_type: str = "auto"):
        super().__init__("clean", {
            "act": CLEAN_ACTION_START,
            "type": clean_type
        })


class CleanPause(Command):

    def __init__(self):
        super().__init__("clean", {
            "act": CLEAN_ACTION_PAUSE
        })


class CleanResume(Command):

    def __init__(self):
        super().__init__("clean", {
            "act": CLEAN_ACTION_RESUME
        })


class CleanStop(Command):

    def __init__(self):
        super().__init__("clean", {
            "act": CLEAN_ACTION_STOP
        })


class CleanAbstractArea(Command):

    def __init__(self, area: str, cleanings: int, clean_type: str):
        super().__init__("clean", {
            "act": CLEAN_ACTION_START,
            "content": str(area),  # must be a string
            "count": cleanings,
            "type": clean_type
        })


class CleanCustomArea(CleanAbstractArea):

    def __init__(self, *, map_position: str, cleanings: int = 1):
        super().__init__(map_position, cleanings, "customArea")


class CleanSpotArea(CleanAbstractArea):

    def __init__(self, *, area: str, cleanings: int = 1):
        super().__init__(area, cleanings, "spotArea")


class GetCleanLogs(Command):

    def __init__(self):
        super().__init__("GetCleanLogs")


class GetLifeSpan(Command):

    def __init__(self):
        super().__init__("getLifeSpan", [COMPONENT_MAIN_BRUSH, COMPONENT_SIDE_BRUSH, COMPONENT_FILTER])


class GetCleanInfo(Command):

    def __init__(self, vacuum: Vacuum):
        command_name = "getCleanInfo"
        if vacuum and vacuum.get_class in [
            "bs40nz",  # DEEBOT T8 AIVI
            "a1nNMoAGAsH",  # DEEBOT T8 MAX
            "vdehg6",  # DEEBOT T8 AIVI +
            "no61kx",  # DEEBOT T8 POWER
            "a7lhb1"  # DEEBOT N9+
        ]:
            command_name = "getCleanInfo_V2"
        super().__init__(command_name)


class GetChargeState(Command):

    def __init__(self):
        super().__init__("getChargeState")


class GetBattery(Command):

    def __init__(self):
        super().__init__("getBattery")


class GetFanSpeed(Command):

    def __init__(self):
        super().__init__("getSpeed")


class GetWaterInfo(Command):

    def __init__(self):
        super().__init__("getWaterInfo")


class GetCachedMapInfo(Command):

    def __init__(self):
        super().__init__("getCachedMapInfo")


class GetStats(Command):

    def __init__(self):
        super().__init__("getStats")


class GetMapTrace(Command):

    def __init__(self, trace_start: int = 0):
        super().__init__("getMapTrace", {
            "pointCount": MAP_TRACE_POINT_COUNT,
            "traceStart": trace_start
        })


class GetMinorMap(Command):

    def __init__(self, *, map_id: int, piece_index: int):
        super().__init__("getMinorMap", {
            "mid": map_id,
            "type": "ol",
            "pieceIndex": piece_index
        })


class GetMapSet(Command):

    def __init__(self, map_id: int):
        super().__init__("getMapSet", {
            "mid": map_id,
            "type": "ar"
        })


class GetMapSubSet(Command):

    def __init__(self, *, map_id: int, map_set_id: int, map_type: str, map_subset_id: str):
        super().__init__("getMapSubSet", {
            "mid": map_id,
            "msid": map_set_id,
            "type": map_type,
            "mssid": map_subset_id
        })


class GetPos(Command):

    def __init__(self):
        super().__init__("getPos", ["chargePos", "deebotPos"])


class GetMajorMap(Command):

    def __init__(self):
        super().__init__("getMajorMap")


class GetError(Command):

    def __init__(self):
        super().__init__("getError")
