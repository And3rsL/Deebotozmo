"""Error commands."""
import logging
from typing import Any, Dict

from ..events import ErrorEventDto, StatusEventDto
from ..models import VacuumState
from .common import EventBus, _NoArgsCommand

_LOGGER = logging.getLogger(__name__)


class GetError(_NoArgsCommand):
    """Get error command."""

    name = "getError"

    @classmethod
    def _handle_body_data_dict(cls, event_bus: EventBus, data: Dict[str, Any]) -> bool:
        """Handle message->body->data and notify the correct event subscribers.

        :return: True if data was valid and no error was included
        """
        codes = data.get("code", [])
        if codes:
            # the last error code
            error = codes[-1]

            if error is not None:
                description = _ERROR_CODES.get(error)
                if error != 0:
                    _LOGGER.warning(
                        "Bot in error-state: code=%d, description=%s",
                        error,
                        description,
                    )
                    event_bus.notify(StatusEventDto(True, VacuumState.ERROR))
                event_bus.notify(ErrorEventDto(error, description))
                return True

        _LOGGER.warning("Could not process error message: message=%s", data)
        return False


# from https://github.com/mrbungle64/ecovacs-deebot.js/blob/master/library/errorCodes.js
_ERROR_CODES = {
    -3: "Error parsing response data",
    -2: "Internal error",
    -1: "Host not reachable or communication malfunction",
    0: "NoError: Robot is operational",
    3: "RequestOAuthError: Authentication error",
    7: "log data is not found",
    100: "NoError: Robot is operational",
    101: "BatteryLow: Low battery",
    102: "HostHang: Robot is off the floor",
    103: "WheelAbnormal: Driving Wheel malfunction",
    104: "DownSensorAbnormal: Excess dust on the Anti-Drop Sensors",
    105: "Stuck: Robot is stuck",
    106: "SideBrushExhausted: Side Brushes have expired",
    107: "DustCaseHeapExhausted: Dust case filter expired",
    108: "SideAbnormal: Side Brushes are tangled",
    109: "RollAbnormal: Main Brush is tangled",
    110: "NoDustBox: Dust Bin Not installed",
    111: "BumpAbnormal: Bump sensor stuck",
    112: 'LDS: LDS "Laser Distance Sensor" malfunction',
    113: "MainBrushExhausted: Main brush has expired",
    114: "DustCaseFilled: Dust bin full",
    115: "BatteryError:",
    116: "ForwardLookingError:",
    117: "GyroscopeError:",
    118: "StrainerBlock:",
    119: "FanError:",
    120: "WaterBoxError:",
    201: "AirFilterUninstall:",
    202: "UltrasonicComponentAbnormal",
    203: "SmallWheelError",
    204: "WheelHang",
    205: "IonSterilizeExhausted",
    206: "IonSterilizeAbnormal",
    207: "IonSterilizeFault",
    404: "Recipient unavailable",
    500: "Request Timeout",
    601: "ERROR_ClosedAIVISideAbnormal",
    602: "ClosedAIVIRollAbnormal",
}
