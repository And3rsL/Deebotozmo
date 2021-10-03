"""Deebot commands."""
from typing import Dict, List, Optional, Union

from deebotozmo.constants import MAP_TRACE_POINT_COUNT
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


class GetCachedMapInfo(Command):
    """Get cached map info command."""

    def __init__(self) -> None:
        super().__init__("getCachedMapInfo")


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
