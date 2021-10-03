from deebotozmo.commands import FanSpeedLevel

from .helpers import verify_DisplayNameEnum_unique


def test_FanSpeedLevel_unique():
    verify_DisplayNameEnum_unique(FanSpeedLevel)