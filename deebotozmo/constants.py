CLEAN_MODE_AUTO = 'auto'
CLEAN_MODE_SPOT_AREA = 'spotArea'
CLEAN_MODE_CUSTOM_AREA = 'customArea'

CLEAN_ACTION_START = 'start'
CLEAN_ACTION_PAUSE = 'pause'
CLEAN_ACTION_RESUME = 'resume'
CLEAN_ACTION_STOP = 'stop'

FAN_SPEED_QUIET = 'quiet'
FAN_SPEED_NORMAL = 'normal'
FAN_SPEED_MAX = 'max'
FAN_SPEED_MAXPLUS = 'max+'

WATER_LOW = "low"
WATER_MEDIUM = "medium"
wATER_HIGH = "high"
WATER_ULTRAHIGH = "ultrahigh"

CHARGE_MODE_RETURN = 'return'
CHARGE_MODE_RETURNING = 'returning'
CHARGE_MODE_CHARGING = 'charging'
CHARGE_MODE_IDLE = 'idle'

COMPONENT_SIDE_BRUSH = 'sideBrush'
COMPONENT_MAIN_BRUSH = 'brush'
COMPONENT_FILTER = 'heap'

CLEANING_STATES = {CLEAN_MODE_AUTO, CLEAN_MODE_CUSTOM_AREA, CLEAN_MODE_SPOT_AREA}
CHARGING_STATES = {CHARGE_MODE_CHARGING}

CLEAN_MODE_TO_ECOVACS = {
    CLEAN_MODE_AUTO: 'auto',
    CLEAN_MODE_SPOT_AREA: 'SpotArea',
    CLEAN_MODE_CUSTOM_AREA: 'customArea'
}

CLEAN_ACTION_TO_ECOVACS = {
    CLEAN_ACTION_START: 'start',
    CLEAN_ACTION_PAUSE: 'pause',
    CLEAN_ACTION_RESUME: 'resume'
}

CLEAN_ACTION_FROM_ECOVACS = {
    'start': CLEAN_ACTION_START,
    'pause': CLEAN_ACTION_PAUSE,
    'resume': CLEAN_ACTION_RESUME
}

CLEAN_MODE_FROM_ECOVACS = {
    'auto': CLEAN_MODE_AUTO,
    'spotArea': CLEAN_MODE_SPOT_AREA,
    'customArea': CLEAN_MODE_CUSTOM_AREA
}

FAN_SPEED_TO_ECOVACS = {
    FAN_SPEED_QUIET: 1000,
    FAN_SPEED_NORMAL: 0,
    FAN_SPEED_MAX: 1,
    FAN_SPEED_MAXPLUS: 2
}

FAN_SPEED_FROM_ECOVACS = {
    1000: FAN_SPEED_QUIET,
    0: FAN_SPEED_NORMAL,
    1: FAN_SPEED_MAX,
    2: FAN_SPEED_MAXPLUS
}

WATER_LEVEL_TO_ECOVACS = {
    WATER_LOW: 1,
    WATER_MEDIUM: 2,
    wATER_HIGH: 3,
    WATER_ULTRAHIGH: 4
}

WATER_LEVEL_FROM_ECOVACS = {
    1: WATER_LOW,
    2: WATER_MEDIUM,
    3: wATER_HIGH,
    4: WATER_ULTRAHIGH
}

CHARGE_MODE_TO_ECOVACS = {
    CHARGE_MODE_RETURN: 'go',
    CHARGE_MODE_RETURNING: 'going',
    CHARGE_MODE_CHARGING: 'charging',
    CHARGE_MODE_IDLE: 'idle'
}

CHARGE_MODE_FROM_ECOVACS = {
    'going': CHARGE_MODE_RETURNING,
    'charging': CHARGE_MODE_CHARGING,
    'idle': CHARGE_MODE_IDLE
}

COMPONENT_FROM_ECOVACS = {
    'brush': COMPONENT_MAIN_BRUSH,
    'sideBrush': COMPONENT_SIDE_BRUSH,
    'heap': COMPONENT_FILTER
}

ROOMS_FROM_ECOVACS = {
    0: 'Default',
    1: 'Living Room',
    2: 'Dining Room',
    3: 'Bedroom',
    4: 'Study',
    5: 'Kitchen',
    6: 'Bathroom',
    7: 'Laundry',
    8: 'Lounge',
    9: 'Storeroom',
    10: 'Kids room',
    11: 'Sunroom',
    12: 'Corridor',
    13: 'Balcony',
    14: 'Gym'
}

# from https://github.com/mrbungle64/ecovacs-deebot.js/blob/master/library/errorCodes.js
ERROR_CODES = {
    -3: 'Error parsing response data',
    -2: 'Internal error',
    -1: 'Host not reachable or communication malfunction',
    0: 'NoError: Robot is operational',
    3: 'RequestOAuthError: Authentication error',
    7: 'log data is not found',
    100: 'NoError: Robot is operational',
    101: 'BatteryLow: Low battery',
    102: 'HostHang: Robot is off the floor',
    103: 'WheelAbnormal: Driving Wheel malfunction',
    104: 'DownSensorAbnormal: Excess dust on the Anti-Drop Sensors',
    105: 'Stuck: Robot is stuck',
    106: 'SideBrushExhausted: Side Brushes have expired',
    107: 'DustCaseHeapExhausted: Dust case filter expired',
    108: 'SideAbnormal: Side Brushes are tangled',
    109: 'RollAbnormal: Main Brush is tangled',
    110: 'NoDustBox: Dust Bin Not installed',
    111: 'BumpAbnormal: Bump sensor stuck',
    112: 'LDS: LDS "Laser Distance Sensor" malfunction',
    113: 'MainBrushExhausted: Main brush has expired',
    114: 'DustCaseFilled: Dust bin full',
    115: 'BatteryError:',
    116: 'ForwardLookingError:',
    117: 'GyroscopeError:',
    118: 'StrainerBlock:',
    119: 'FanError:',
    120: 'WaterBoxError:',
    201: 'AirFilterUninstall:',
    202: 'UltrasonicComponentAbnormal',
    203: 'SmallWheelError',
    204: 'WheelHang',
    205: 'IonSterilizeExhausted',
    206: 'IonSterilizeAbnormal',
    207: 'IonSterilizeFault',
    404: 'Recipient unavailable',
    500: 'Request Timeout',
    601: 'ERROR_ClosedAIVISideAbnormal',
    602: 'ClosedAIVIRollAbnormal',
}

MAP_TRACE_POINT_COUNT = 200
