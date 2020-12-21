import hashlib
import logging
import random
import requests
import stringcase
import os
import json
import threading
import urllib3

from base64 import b64decode, b64encode
from sleekxmppfs import ClientXMPP, Callback, MatchXPath
from sleekxmppfs.exceptions import XMPPError
from .map import *
from .constants import *
from .ecovacsiotmq import *

_LOGGER = logging.getLogger(__name__)

class EcoVacsAPI:
    CLIENT_KEY = "eJUWrzRv34qFSaYk"
    SECRET = "Cyu5jcR4zyK6QEPn1hdIGXB5QIDAQABMA0GC"
    PUBLIC_KEY = 'MIIB/TCCAWYCCQDJ7TMYJFzqYDANBgkqhkiG9w0BAQUFADBCMQswCQYDVQQGEwJjbjEVMBMGA1UEBwwMRGVmYXVsdCBDaXR5MRwwGgYDVQQKDBNEZWZhdWx0IENvbXBhbnkgTHRkMCAXDTE3MDUwOTA1MTkxMFoYDzIxMTcwNDE1MDUxOTEwWjBCMQswCQYDVQQGEwJjbjEVMBMGA1UEBwwMRGVmYXVsdCBDaXR5MRwwGgYDVQQKDBNEZWZhdWx0IENvbXBhbnkgTHRkMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDb8V0OYUGP3Fs63E1gJzJh+7iqeymjFUKJUqSD60nhWReZ+Fg3tZvKKqgNcgl7EGXp1yNifJKUNC/SedFG1IJRh5hBeDMGq0m0RQYDpf9l0umqYURpJ5fmfvH/gjfHe3Eg/NTLm7QEa0a0Il2t3Cyu5jcR4zyK6QEPn1hdIGXB5QIDAQABMA0GCSqGSIb3DQEBBQUAA4GBANhIMT0+IyJa9SU8AEyaWZZmT2KEYrjakuadOvlkn3vFdhpvNpnnXiL+cyWy2oU1Q9MAdCTiOPfXmAQt8zIvP2JC8j6yRTcxJCvBwORDyv/uBtXFxBPEC6MDfzU2gKAaHeeJUWrzRv34qFSaYkYta8canK+PSInylQTjJK9VqmjQ'
    MAIN_URL_FORMAT = 'https://eco-{country}-api.ecovacs.com/v1/private/{country}/{lang}/{deviceId}/{appCode}/{appVersion}/{channel}/{deviceType}'
    MAIN_URL_CHINESE_FORMAT = 'https://gl-cn-api.ecovacs.cn/v1/private/{country}/{lang}/{deviceId}/{appCode}/{appVersion}/{channel}/{deviceType}'
    USER_URL_FORMAT = 'https://users-{continent}.ecouser.net:8000/user.do'
    PORTAL_URL_FORMAT = 'https://portal-{continent}.ecouser.net/api'

    USERSAPI = 'users/user.do'
    IOTDEVMANAGERAPI = 'iot/devmanager.do' # IOT Device Manager - This provides control of "IOT" products via RestAPI
    PRODUCTAPI = 'pim/product' # Leaving this open, the only endpoint known currently is "Product IOT Map" -  pim/product/getProductIotMap - This provides a list of "IOT" products.  Not sure what this provides the app.
        
    REALM = 'ecouser.net'

    def __init__(self, device_id, account_id, password_hash, country, continent, verify_ssl=True):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.meta = {
            'country': country,
            'lang': 'en',
            'deviceId': device_id,
            'appCode': 'i_eco_e',
            'appVersion': '1.3.5',
            'channel': 'c_googleplay',
            'deviceType': '1'
        }
        
        self.verify_ssl = str_to_bool_or_cert(verify_ssl)
        _LOGGER.debug("Setting up EcoVacsAPI")
        self.resource = device_id[0:8]
        self.country = country
        self.continent = continent
        login_info = self.__call_main_api('user/login',
                                          ('account', self.encrypt(account_id)),
                                          ('password', self.encrypt(password_hash)))
        self.uid = login_info['uid']
        self.login_access_token = login_info['accessToken']
        self.auth_code = self.__call_main_api('user/getAuthCode',
                                              ('uid', self.uid),
                                              ('accessToken', self.login_access_token))['authCode']
        login_response = self.__call_login_by_it_token()
        self.user_access_token = login_response['token']
        if login_response['userId'] != self.uid:
            logging.debug("Switching to shorter UID " + login_response['userId'])
            self.uid = login_response['userId']
        logging.debug("EcoVacsAPI connection complete")

    def __sign(self, params):
        result = params.copy()
        result['authTimespan'] = int(time.time() * 1000)
        result['authTimeZone'] = 'GMT-8'

        sign_on = self.meta.copy()
        sign_on.update(result)
        sign_on_text = EcoVacsAPI.CLIENT_KEY + ''.join(
            [k + '=' + str(sign_on[k]) for k in sorted(sign_on.keys())]) + EcoVacsAPI.SECRET

        result['authAppkey'] = EcoVacsAPI.CLIENT_KEY
        result['authSign'] = self.md5(sign_on_text)
        return result

    def __call_main_api(self, function, *args):
        _LOGGER.debug("calling main api {} with {}".format(function, args))
        params = OrderedDict(args)
        params['requestId'] = self.md5(time.time())

        if self.country.lower() == 'cn':
            url = (EcoVacsAPI.MAIN_URL_CHINESE_FORMAT + "/" + function).format(**self.meta)
        else:
            url = (EcoVacsAPI.MAIN_URL_FORMAT + "/" + function).format(**self.meta)

        api_response = requests.get(url, self.__sign(params), verify=self.verify_ssl)
        json = api_response.json()
        _LOGGER.debug("got {}".format(json))
        if json['code'] == '0000':
            return json['data']
        elif json['code'] == '1005':
            _LOGGER.warning("incorrect email or password")
            raise ValueError("incorrect email or password")
        else:
            _LOGGER.error("call to {} failed with {}".format(function, json))
            raise RuntimeError("failure code {} ({}) for call {} and parameters {}".format(
                json['code'], json['msg'], function, args))

    def __call_user_api(self, function, args):
        _LOGGER.debug("calling user api {} with {}".format(function, args))
        params = {'todo': function}
        params.update(args)
        response = requests.post(EcoVacsAPI.USER_URL_FORMAT.format(continent=self.continent), json=params, verify=self.verify_ssl)
        json = response.json()
        _LOGGER.debug("got {}".format(json))
        if json['result'] == 'ok':
            return json
        else:
            _LOGGER.error("call to {} failed with {}".format(function, json))
            raise RuntimeError(
                "failure {} ({}) for call {} and parameters {}".format(json['error'], json['errno'], function, params))

    def __call_portal_api(self, api, function, args, verify_ssl=True, **kwargs):      
        
        if api == self.USERSAPI:
            params = {'todo': function}
            params.update(args)
        else:
            params = {}
            params.update(args)      
        
        continent = self.continent
        if 'continent' in kwargs:
            continent = kwargs.get('continent')

        url = (EcoVacsAPI.PORTAL_URL_FORMAT + "/" + api).format(continent=continent, **self.meta)        
        
        response = requests.post(url, json=params, verify=verify_ssl)        

        json = response.json()
        _LOGGER.debug("got {}".format(json))
        if api == self.USERSAPI:    
            if json['result'] == 'ok':
                return json
            elif json['result'] == 'fail':
                if json['error'] == 'set token error.': # If it is a set token error try again
                    if not 'set_token' in kwargs:      
                        _LOGGER.warning("loginByItToken set token error, trying again (2/3)")              
                        return self.__call_portal_api(self.USERSAPI, function, args, verify_ssl=verify_ssl, set_token=1)
                    elif kwargs.get('set_token') == 1:
                        _LOGGER.warning("loginByItToken set token error, trying again with ww (3/3)")              
                        return self.__call_portal_api(self.USERSAPI, function, args, verify_ssl=verify_ssl, set_token=2, continent="ww")
                    else:
                        _LOGGER.warning("loginByItToken set token error, failed after 3 attempts")
                                    
        if api.startswith(self.PRODUCTAPI):
            if json['code'] == 0:
                return json      

        else:
            _LOGGER.error("call to {} failed with {}".format(function, json))
            raise RuntimeError(
                "failure {} ({}) for call {} and parameters {}".format(json['error'], json['errno'], function, params))

    def __call_login_by_it_token(self):
        return self.__call_portal_api(self.USERSAPI,'loginByItToken',
                                    {'country': self.meta['country'].upper(),
                                     'resource': self.resource,
                                     'realm': EcoVacsAPI.REALM,
                                     'userId': self.uid,
                                     'token': self.auth_code}
                                    , verify_ssl=self.verify_ssl)
  
    def getdevices(self):
        return  self.__call_portal_api(self.USERSAPI,'GetDeviceList', {
            'userid': self.uid,
            'auth': {
                'with': 'users',
                'userid': self.uid,
                'realm': EcoVacsAPI.REALM,
                'token': self.user_access_token,
                'resource': self.resource
            }
        }, verify_ssl=self.verify_ssl)['devices']

    def getiotProducts(self):
        return self.__call_portal_api(self.PRODUCTAPI + '/getProductIotMap','', {
            'channel': '',
            'auth': {
                'with': 'users',
                'userid': self.uid,
                'realm': EcoVacsAPI.REALM,
                'token': self.user_access_token,
                'resource': self.resource
            }
        }, verify_ssl=self.verify_ssl)['data']

    def SetIOTMQDevices(self, devices):
        #Added for devices that utilize MQTT
        for device in devices:
            if device['company'] == 'eco-ng': #Check if the device is part of the list
                device['iotmq'] = True

        return devices
       
    def devices(self):
        return self.SetIOTMQDevices(self.getdevices())

    @staticmethod
    def md5(text):
        return hashlib.md5(bytes(str(text), 'utf8')).hexdigest()

    @staticmethod
    def encrypt(text):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        key = RSA.import_key(b64decode(EcoVacsAPI.PUBLIC_KEY))
        cipher = PKCS1_v1_5.new(key)
        result = cipher.encrypt(bytes(text, 'utf8'))
        return str(b64encode(result), 'utf8')

class VacBot():
    def __init__(self, user, domain, resource, secret, vacuum, continent, live_map_enabled = True, show_rooms_color = False, verify_ssl=True):

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

        # Populated by component Lifespan reports
        self.components = {}

        # Map Components
        self.__map = Map()
        self.__map.draw_rooms = show_rooms_color
        
        self.live_map = None

        self.lastCleanLogs = []
        self.last_clean_image = None

        #Set none for clients to start        
        self.iotmq = None
        
        self.iotmq = EcoVacsIOTMQ(user, domain, resource, secret, continent, vacuum, EcoVacsAPI.REALM, EcoVacsAPI.PORTAL_URL_FORMAT, verify_ssl=verify_ssl)
        self.iotmq.subscribe_to_ctls(self._handle_ctl)

        self.live_map_enabled = live_map_enabled

        # Stats
        self.stats_area = None
        self.stats_cid = None
        self.stats_time = None
        self.stats_type = None

        # Threads
        self.thread_statuses = threading.Thread(target=self.refresh_statuses, daemon=False, name="schedule_thread_statuses")
        self.thread_livemap = threading.Thread(target=self.refresh_liveMap, daemon=False, name="schedule_thread_livemap")
        self.thread_components = threading.Thread(target=self.refresh_components, daemon=False, name="schedule_thread_components")

    def connect_and_wait_until_ready(self):
        self.iotmq.connect_and_wait_until_ready()
        self.iotmq.schedule(30, self.send_ping)

    def _handle_ctl(self, ctl):
        method = '_handle_' + ctl['event']
        if hasattr(self, method):
            getattr(self, method)(ctl)

    def _handle_error(self, event):
        if 'error' in event:
            error = event['error']
        elif 'errs' in event:
            error = event['errs']

        if not error == '':
            _LOGGER.warning("*** error = " + error)

    def _handle_life_span(self, event):
        response = event['body']['data'][0]
        type = response['type']

        try:
            type = COMPONENT_FROM_ECOVACS[type]
        except KeyError:
            _LOGGER.warning("Unknown component type: '" + type + "'")
            
        left = int(response['left'])
        total = int(response['total'])
			
        lifespan = (left/total) * 100
       
        self.components[type] = lifespan

    def _handle_fan_speed(self, event):
        response = event['body']['data']
        speed = response['speed']

        try:
            speed = FAN_SPEED_FROM_ECOVACS[speed]
        except KeyError:
            _LOGGER.warning("Unknown fan speed: '" + str(speed) + "'")
      
        self.fan_speed = speed

    def _handle_clean_logs(self, event):
        response = event.get('logs')
        self.lastCleanLogs = []

        # Ecovacs API is changing their API, this request may not working properly
        if response is not None and len(response) >= 0:
            self.last_clean_image = response[0]['imageUrl']
            for cleanLog in response:
                self.lastCleanLogs.append({'timestamp': cleanLog['ts'], 'imageUrl': cleanLog['imageUrl'],
                                           'type': cleanLog['type']})
                                           
    def _handle_water_info(self, event):
        response = event['body']['data']
        amount = response['amount']

        try:
            amount = WATER_LEVEL_FROM_ECOVACS[amount]
        except KeyError:
            _LOGGER.warning("Unknown water level: '" + str(amount) + "'")
      
        self.water_level = amount
        self.mop_attached = bool(response.get("enable"))

    def _handle_clean_report(self, event):
        response = event['body']['data']
        if response['state'] == 'clean':
            if response['trigger'] == 'app' or response['trigger'] == 'shed':
                if response['cleanState']['motionState'] == 'working':
                    self.vacuum_status = 'STATE_CLEANING'
                elif response['cleanState']['motionState'] == 'pause':
                    self.vacuum_status = 'STATE_PAUSED'
                else:
                    self.vacuum_status = 'STATE_RETURNING'
            elif response['trigger'] == 'alert':
                self.vacuum_status = 'STATE_ERROR'

    def _handle_map_trace(self, event):
        response = event['body']['data']
        totalCount = int(response['totalCount'])
        traceStart = int(response['traceStart'])
        pointCount = 200

        # No trace value avaiable
        if 'traceValue' in response:
            if traceStart == 0:
                self.__map.traceValues = []

            _LOGGER.debug("Trace Request: TotalCount=" + str(totalCount) + ' traceStart=' + str(traceStart))
            self.__map.updateTracePoints(response['traceValue'])

            if (traceStart+pointCount) < totalCount:
                self.exc_command('getMapTrace',{'pointCount':pointCount,'traceStart':traceStart+pointCount})


    def _handle_set_position(self, event):
        response = event['body']['data']

        # Charger
        if 'chargePos' in response:
            charger_pos = response['chargePos']
            self.__map.updateChargerPosition(charger_pos[0]['x'], charger_pos[0]['y'])

        if 'deebotPos' in response:
            # Robot
            robot_pos = response['deebotPos']
            self.__map.updateRobotPosition(robot_pos['x'], robot_pos['y'])

    def _handle_minor_map(self, event):
        response = event['body']['data']

        _LOGGER.debug("Handled minor_map : " + str(response['pieceIndex']))

        self.__map.AddMapPiece(response['pieceIndex'], response['pieceValue'])

    def _handle_major_map(self, event):
        _LOGGER.debug("_handle_major_map begin")
        response = event['body']['data']
        
        values = response['value'].split(",")

        for i in range(64):
            if self.__map.isUpdatePiece(i, values[i]):
                _LOGGER.debug("MapPiece" + str(i) + ' needs to be updated')
                self.exc_command('getMinorMap', {'mid': response['mid'],'type': 'ol', 'pieceIndex': i})

    def _handle_cached_map(self, event):
        response = event['body']['data']
        
        try:
            mapid = response['info'][0]['mid']
            self.__map.rooms = []
            self.exc_command('getMapSet', {'mid': mapid,'type': 'ar'})
        except:
            _LOGGER.warning("MapID not found -- did you finish your first auto cleaning?")

    def _handle_map_set(self, event):
        response = event['body']['data']
        
        mid = response['mid']
        msid = response['msid']
        typemap = response['type']

        for s in response['subsets']:
            self.exc_command('getMapSubSet', {'mid': mid,'msid': msid,'type': typemap, 'mssid': s['mssid']})

    def _handle_map_sub_set(self, event):
        response = event['body']['data']
        subtype = int(response['subtype'])
        value = response['value']

        self.__map.rooms.append({'subtype':ROOMS_FROM_ECOVACS[subtype],'id': int(response['mssid']), 'values': value})

    def _handle_battery_info(self, event):
        response = event['body']
        try:
            self.battery_status = response['data']['value']
        except ValueError:
            _LOGGER.warning("couldn't parse battery status " + response)

    def _handle_charge_state(self, event):
        response = event['body']
        status = 'none'
        if response['code'] == 0:
            if response['data']['isCharging'] == 1:
                status = 'STATE_DOCKED'
        else:
            if response['msg'] == 'fail' and response['code'] == '30007': #Already charging
                status = 'STATE_DOCKED'
            elif response['msg'] == 'fail' and response['code'] == '5': #Busy with another command
                status = 'STATE_ERROR'
            elif response['msg'] == 'fail' and response['code'] == '3': #Bot in stuck state, example dust bin out
                status = 'STATE_ERROR'
            else: 
                _LOGGER.error("Unknown charging status '" + response['code'] + "'") #Log this so we can identify more errors    

        if status != 'none':
            self.vacuum_status = status

    def _handle_stats(self, event):
        response = event['body']

        if response['code'] == 0:
            if 'area' in  response['data']:
                self.stats_area = response['data']['area']
            
            if 'cid' in  response['data']:
                self.stats_cid = response['data']['cid']
            
            if 'time' in  response['data']:
                self.stats_time = response['data']['time']

            if 'type' in response['data']:
                self.stats_type = response['data']['type']
        else:
            _LOGGER.error("Error in finding stats, status code = " + response['code']) #Log this so we can identify more errors    

    def _vacuum_address(self):
        return self.vacuum['did']

    def send_ping(self):
        try:
            if not self.iotmq.send_ping():
                raise RuntimeError()                
            else:
                self.is_available = True
        except XMPPError as err:
            _LOGGER.warning("Ping did not reach VacBot. Will retry.")
            _LOGGER.warning("*** Error type: " + err.etype)
            _LOGGER.warning("*** Error condition: " + err.condition)
            self._failed_pings += 1
            if self._failed_pings >= 4:
                self.is_available = False

        except RuntimeError as err:
            _LOGGER.warning("Ping did not reach VacBot. Will retry.")
            self._failed_pings += 1
            if self._failed_pings >= 4:
                self.is_available = False

        else:
            self._failed_pings = 0
            self.is_available = True

    def refresh_components(self):
        try:
            _LOGGER.debug("[refresh_components] Begin")
            self.exc_command('getLifeSpan',[COMPONENT_TO_ECOVACS["brush"]])
            self.exc_command('getLifeSpan',[COMPONENT_TO_ECOVACS["sideBrush"]])
            self.exc_command('getLifeSpan',[COMPONENT_TO_ECOVACS["heap"]])
            self.exc_command('GetCleanLogs')
        except XMPPError as err:
            _LOGGER.warning("Component refresh requests failed to reach VacBot. Will try again later.")
            _LOGGER.warning("*** Error type: " + err.etype)
            _LOGGER.warning("*** Error condition: " + err.condition)

    def refresh_statuses(self):
        try:
            _LOGGER.debug("[refresh_statuses] Begin")
            self.exc_command('getCleanInfo')
            self.exc_command('getChargeState')
            self.exc_command('getBattery')
            self.exc_command('getSpeed')
            self.exc_command('getWaterInfo')
            self.exc_command('getCachedMapInfo')
            self.exc_command('getStats')
        except XMPPError as err:
            _LOGGER.warning("Initial status requests failed to reach VacBot. Will try again on next ping.")
            _LOGGER.warning("*** Error type: " + err.etype)
            _LOGGER.warning("*** Error condition: " + err.condition)

    def refresh_liveMap(self):
        try:
            _LOGGER.debug("[refresh_liveMap] Begin")
            self.exc_command('getMapTrace',{'pointCount':200,'traceStart':0})
            self.exc_command('getPos',['chargePos','deebotPos'])
            self.exc_command('getMajorMap')
            self.live_map = self.__map.GetBase64Map()
        except XMPPError as err:
            _LOGGER.warning("Initial live map failed to reach VacBot. Will try again on next ping.")
            _LOGGER.warning("*** Error type: " + err.etype)
            _LOGGER.warning("*** Error condition: " + err.condition)

    def request_all_statuses(self):
        if not self.thread_statuses.isAlive():
            self.thread_statuses = threading.Thread(target=self.refresh_statuses, daemon=False, name="schedule_thread_statuses")
            self.thread_statuses.start()

        if self.live_map_enabled:
            if not self.thread_livemap.isAlive():
                self.thread_livemap = threading.Thread(target=self.refresh_liveMap, daemon=False, name="schedule_thread_livemap")
                self.thread_livemap.start()
                
        if not self.thread_components.isAlive():
            self.thread_components = threading.Thread(target=self.refresh_components, daemon=False, name="schedule_thread_components")
            self.thread_components.start()
    
    def setScheduleUpdates(self, livemap_cycle = 15, status_cycle = 30, components_cycle = 60):
        # It will refresh all statuses very X seconds
        if self.live_map_enabled:
            self.iotmq.schedule(livemap_cycle, self.refresh_liveMap)

        self.iotmq.schedule(status_cycle, self.refresh_statuses)
        self.iotmq.schedule(components_cycle, self.refresh_components)

    def getSavedRooms(self):
        return self.__map.rooms

    def getTypeRooms(self):
        return ROOMS_FROM_ECOVACS

	#Common ecovacs commands
    def Clean(self, type='auto'):
        _LOGGER.debug("[Command] Clean Start TYPE: " + type)
        self.exc_command('clean', {'act': CLEAN_ACTION_START,'type': type})
        self.refresh_statuses()

    def CleanPause(self):
        _LOGGER.debug("[Command] Clean Pause")
        self.exc_command('clean', {'act': CLEAN_ACTION_PAUSE})
        self.refresh_statuses()

    def CleanResume(self):
        if self.vacuum_status == 'STATE_PAUSED':
            _LOGGER.debug("[Command] Clean Resume - Resume")
            self.exc_command('clean', {'act': CLEAN_ACTION_RESUME})
        else:
            _LOGGER.debug("[Command] Clean Resume - ActionStart")
            self.exc_command('clean', {'act': CLEAN_ACTION_START,'type': 'auto'})

        self.refresh_statuses()

    def Charge(self):
        _LOGGER.debug("[Command] Charge")
        self.exc_command('charge', {'act': CHARGE_MODE_TO_ECOVACS['return']})
        self.refresh_statuses()

    def PlaySound(self):
        _LOGGER.debug("[Command] PlaySound")
        self.exc_command('playSound', {'count': 1, 'sid': 30})

    def Relocate(self):
        _LOGGER.debug("[Command] Relocate")
        self.exc_command('setRelocationState', {'mode': 'manu'})

    def GetCleanLogs(self):
        _LOGGER.debug("[Command] GetCleanLogs")
        self.exc_command('GetCleanLogs')

    def CustomArea(self, map_position, cleanings=1):
        _LOGGER.debug("[Command] CustomArea content=" + str(map_position) + " count=" + str(cleanings))
        self.exc_command('clean', {'act': 'start', 'content': str(map_position), 'count': int(cleanings), 'type': 'customArea'})
        self.refresh_statuses()

    def SpotArea(self, area, cleanings=1):
        _LOGGER.debug("[Command] SpotArea content=" + str(area) + " count=" + str(cleanings))
        self.exc_command('clean', {'act': 'start', 'content': str(area), 'count': int(cleanings), 'type': 'spotArea'})
        self.refresh_statuses()

    def SetFanSpeed(self, speed=1):
        _LOGGER.debug("[Command] setSpeed speed=" + str(speed))
        self.exc_command('setSpeed', {'speed': FAN_SPEED_TO_ECOVACS[speed]})
        self.refresh_statuses()

    def SetWaterLevel(self, amount=1):
        _LOGGER.debug("[Command] setWaterInfo amount=" + str(amount))
        self.exc_command('setWaterInfo', {'amount': WATER_LEVEL_TO_ECOVACS[amount], 'enable': 0})
        self.refresh_statuses()

    def exc_command(self, action, params=None, **kwargs):
        self.send_command(VacBotCommand(action, params))

    def send_command(self, action):
        #IOTMQ issues commands via RestAPI, and listens on MQTT for status updates
        self.iotmq.send_command(action, self._vacuum_address())  #IOTMQ devices need the full action for additional parsing

    def disconnect(self, wait=False):
        self.iotmq._disconnect()

class VacBotCommand:
    def __init__(self, name, args=None, **kwargs):
        if args is None:
            args = {}
        self.name = name
        self.args = args

    def __str__(self, *args, **kwargs):
        return self.command_name() + " command"

    def command_name(self):
        return self.__class__.__name__.lower()