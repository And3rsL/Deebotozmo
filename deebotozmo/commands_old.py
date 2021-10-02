"""Deebot commands."""
from typing import Dict, List, Optional, Union

from deebotozmo.constants import (
    CLEAN_ACTION_PAUSE,
    CLEAN_ACTION_RESUME,
    CLEAN_ACTION_START,
    CLEAN_ACTION_STOP,
    COMPONENT_FILTER,
    COMPONENT_MAIN_BRUSH,
    COMPONENT_SIDE_BRUSH,
    MAP_TRACE_POINT_COUNT,
)
from deebotozmo.models import Vacuum


class Command:
    """Base command object."""

    def __init__(self, name: str, args: Optional[Union[Dict, List]] = None) -> None:
        if args is None:
            args = {}
        self._name = name
        self._args = args

    @property
    def name(self) -> str:
        """Command name."""
        return self._name

    @property
    def args(self) -> Union[Dict, List]:
        """Command additional arguments."""
        return self._args


class Relocate(Command):
    """Relocate command."""

    def __init__(self) -> None:
        super().__init__("setRelocationState", {"mode": "manu"})


class PlaySound(Command):
    """Play sound command."""

    def __init__(self) -> None:
        super().__init__("playSound", {"count": 1, "sid": 30})


class Charge(Command):
    """Charge command."""

    def __init__(self) -> None:
        super().__init__("charge", {"act": "go"})


class CleanStart(Command):
    """Clean start command."""

    def __init__(self, clean_type: str = "auto") -> None:
        super().__init__("clean", {"act": CLEAN_ACTION_START, "type": clean_type})


class CleanPause(Command):
    """Clean Pause command."""

    def __init__(self) -> None:
        super().__init__("clean", {"act": CLEAN_ACTION_PAUSE})


class CleanResume(Command):
    """Clean resume command."""

    def __init__(self) -> None:
        super().__init__("clean", {"act": CLEAN_ACTION_RESUME})


class CleanStop(Command):
    """Clean stop command."""

    def __init__(self) -> None:
        super().__init__("clean", {"act": CLEAN_ACTION_STOP})


class CleanAbstractArea(Command):
    """Abstract clean area command."""

    def __init__(self, area: str, cleanings: int, clean_type: str) -> None:
        super().__init__(
            "clean",
            {
                "act": CLEAN_ACTION_START,
                "content": str(area),  # must be a string
                "count": cleanings,
                "type": clean_type,
            },
        )


class CleanCustomArea(CleanAbstractArea):
    """Custom area command."""

    def __init__(self, *, map_position: str, cleanings: int = 1) -> None:
        super().__init__(map_position, cleanings, "customArea")


class CleanSpotArea(CleanAbstractArea):
    """Clean spot command."""

    def __init__(self, *, area: str, cleanings: int = 1) -> None:
        super().__init__(area, cleanings, "spotArea")


class GetCleanLogs(Command):
    """Get clean logs command."""

    def __init__(self) -> None:
        super().__init__("GetCleanLogs")


class GetLifeSpan(Command):
    """Get life span command."""

    def __init__(self) -> None:
        super().__init__(
            "getLifeSpan",
            [COMPONENT_MAIN_BRUSH, COMPONENT_SIDE_BRUSH, COMPONENT_FILTER],
        )


class GetCleanInfo(Command):
    """Get clean info command."""

    def __init__(self, vacuum: Vacuum) -> None:
        command_name = "getCleanInfo"
        if vacuum and vacuum.get_class in [
            "bs40nz",  # DEEBOT T8 AIVI
            "a1nNMoAGAsH",  # DEEBOT T8 MAX
            "vdehg6",  # DEEBOT T8 AIVI +
            "no61kx",  # DEEBOT T8 POWER
            "a7lhb1",  # DEEBOT N9+
        ]:
            command_name = "getCleanInfo_V2"
        super().__init__(command_name)


class GetChargeState(Command):
    """Get charge state command."""

    def __init__(self) -> None:
        super().__init__("getChargeState")


class GetBattery(Command):
    """Get battery command."""

    def __init__(self) -> None:
        super().__init__("getBattery")


class GetCachedMapInfo(Command):
    """Get cached map info command."""

    def __init__(self) -> None:
        super().__init__("getCachedMapInfo")


class GetStats(Command):
    """Get stats command."""

    def __init__(self) -> None:
        super().__init__("getStats")


class GetMapTrace(Command):
    """Get map trace command."""

    def __init__(self, trace_start: int = 0) -> None:
        super().__init__(
            "getMapTrace",
            {"pointCount": MAP_TRACE_POINT_COUNT, "traceStart": trace_start},
        )


class GetMinorMap(Command):
    """Get minor map command."""

    def __init__(self, *, map_id: int, piece_index: int) -> None:
        super().__init__(
            "getMinorMap", {"mid": map_id, "type": "ol", "pieceIndex": piece_index}
        )


class GetMapSet(Command):
    """Get map set command."""

    def __init__(self, map_id: str) -> None:
        super().__init__("getMapSet", {"mid": map_id, "type": "ar"})


class GetMapSubSet(Command):
    """Get map subset command."""

    def __init__(
        self, *, map_id: str, map_set_id: str, map_type: str, map_subset_id: str
    ) -> None:
        super().__init__(
            "getMapSubSet",
            {
                "mid": map_id,
                "msid": map_set_id,
                "type": map_type,
                "mssid": map_subset_id,
            },
        )


class GetPos(Command):
    """Get position command."""

    def __init__(self) -> None:
        super().__init__("getPos", ["chargePos", "deebotPos"])


class GetMajorMap(Command):
    """Get major map command."""

    def __init__(self) -> None:
        super().__init__("getMajorMap")


class GetError(Command):
    """Get error command."""

    def __init__(self) -> None:
        super().__init__("getError")
