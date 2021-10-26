from deebotozmo.events import WaterAmount
from tests.helpers import verify_DisplayNameEnum_unique


def test_WaterLevel_unique():
    verify_DisplayNameEnum_unique(WaterAmount)

