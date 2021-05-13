from deebotozmo import FAN_SPEED_TO_ECOVACS, FAN_SPEED_NORMAL, WATER_LEVEL_TO_ECOVACS, WATER_MEDIUM, \
    CLEAN_ACTION_START, CLEAN_ACTION_PAUSE, CLEAN_ACTION_RESUME, COMPONENT_TO_ECOVACS
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
            "speed": FAN_SPEED_TO_ECOVACS.get(speed, FAN_SPEED_NORMAL)
        })


class SetWaterLevel(Command):

    def __init__(self, amount: str):
        super().__init__("setWaterInfo", {
            "amount": WATER_LEVEL_TO_ECOVACS.get(amount, WATER_MEDIUM),
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
            "act": "charging"
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


class CleanAbstractArea(Command):

    def __init__(self, area: str, cleanings: int, clean_type: str):
        super().__init__("clean", {
            "act": CLEAN_ACTION_START,
            "content": area,
            "count": cleanings,
            "type": clean_type
        })


class CleanCustomArea(CleanAbstractArea):

    def __init__(self, map_position: str, cleanings: int = 1):
        super().__init__(map_position, cleanings, "customArea")


class CleanSpotArea(CleanAbstractArea):

    def __init__(self, area: str, cleanings: int = 1):
        super().__init__(area, cleanings, "spotArea")


class GetCleanLogs(Command):

    def __init__(self):
        super().__init__("GetCleanLogs")


class GetLifeSpan(Command):

    def __init__(self, component: str):
        super().__init__("getLifeSpan", [COMPONENT_TO_ECOVACS[component]])


class GetCleanInfo(Command):

    def __init__(self, vacuum: Vacuum):
        command_name = "getCleanInfo"
        if vacuum.get_class in ["bs40nz", "a1nNMoAGAsH", "vdehg6", "no61kx"]:
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
