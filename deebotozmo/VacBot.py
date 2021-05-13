from deebotozmo import *
from deebotozmo.commands import *
from deebotozmo.ecovacs_json import EcovacsJSON
from deebotozmo.models import Vacuum, EventEmitter

_LOGGER = logging.getLogger(__name__)


class VacBot:
    def __init__(
            self,
            auth: dict,
            vacuum: Vacuum,
            continent: str,


            country,
            live_map_enabled=True,
            show_rooms_color=False,
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
        self.modelVersion = self.vacuum.device_name

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

    def execute_command(self, command: Command):
        if command.name == CleanResume.name and self.vacuum_status != "STATE_PAUSED":
            command = CleanStart()

        response = self.json.send_command(command, self.vacuum)
        # Todo handle response

    ############### REFRESH ROUTINES ###############################

    def refresh_components(self):
        _LOGGER.debug("[refresh_components] Begin")
        self.execute_command(GetLifeSpan(COMPONENT_MAIN_BRUSH))
        self.execute_command(GetLifeSpan(COMPONENT_SIDE_BRUSH))
        self.execute_command(GetLifeSpan(COMPONENT_FILTER))

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

    def getSavedRooms(self):
        return self.__map.rooms

    def getTypeRooms(self):
        return ROOMS_FROM_ECOVACS
