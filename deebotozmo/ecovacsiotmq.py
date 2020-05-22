import sched
import time
import threading
import ssl
import datetime
import requests
import logging

from collections import OrderedDict
from threading import Event
from paho.mqtt.client import Client  as ClientMQTT
from paho.mqtt import publish as MQTTPublish
from paho.mqtt import subscribe as MQTTSubscribe

_LOGGER = logging.getLogger(__name__)

def str_to_bool_or_cert(s):
    if s == 'True' or s == True:
        return True
    elif s == 'False' or s == False:
        return False    
    else:
        if not s == None:
            if os.path.exists(s): # User could provide a path to a CA Cert as well, which is useful for Bumper
                if os.path.isfile(s):
                    return s
                else:                
                    raise ValueError("Certificate path provided is not a file - {}".format(s))
        
        raise ValueError("Cannot covert {} to a bool or certificate path".format(s))
        

class EcoVacsIOTMQ(ClientMQTT):
    def __init__(self, user, domain, resource, secret, continent, vacuum, realm, portal_url_format, server_address=None, verify_ssl=True):
        ClientMQTT.__init__(self)
        self.ctl_subscribers = []        
        self.user = user
        self.domain = str(domain).split(".")[0] #MQTT is using domain without tld extension
        self.resource = resource
        self.secret = secret
        self.continent = continent
        self.vacuum = vacuum
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler_thread = threading.Thread(target=self.scheduler.run, daemon=True, name="mqtt_schedule_thread")
        self.verify_ssl = str_to_bool_or_cert(verify_ssl)
        self.realm = realm
        self.portal_url_format = portal_url_format

        if server_address is None: 	
            self.hostname = ('mq-{}.ecouser.net'.format(self.continent))
            self.port = 8883
        else:
            saddress = server_address.split(":")
            if len(saddress) > 1:
                self.hostname = saddress[0]
                if RepresentsInt(saddress[1]):
                    self.port = int(saddress[1])
                else:
                    self.port = 8883                    

        self._client_id = self.user + '@' + self.domain.split(".")[0] + '/' + self.resource        
        self.username_pw_set(self.user + '@' + self.domain, secret)

        self.ready_flag = Event()

    def connect_and_wait_until_ready(self):        
        self._on_log = self.on_log #This provides more logging than needed, even for debug
        self._on_connect = self.on_connect        

        #TODO: This is pretty insecure and accepts any cert, maybe actually check?
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self.tls_set_context(ssl_ctx)
        self.tls_insecure_set(True)
        self.connect(self.hostname, self.port)
        self.loop_start()        
        self.wait_until_ready()

    def subscribe_to_ctls(self, function):
        self.ctl_subscribers.append(function)   

    def _disconnect(self):
        self.disconnect() #disconnect mqtt connection
        self.scheduler.empty() #Clear schedule queue  

    def _run_scheduled_func(self, timer_seconds, timer_function):
        timer_function()
        self.schedule(timer_seconds, timer_function)

    def schedule(self, timer_seconds, timer_function):
        self.scheduler.enter(timer_seconds, 1, self._run_scheduled_func,(timer_seconds, timer_function))
        if not self.scheduler_thread.isAlive():
            self.scheduler_thread.start()
        
    def wait_until_ready(self):
        self.ready_flag.wait()

    def on_connect(self, client, userdata, flags, rc):        
        if rc != 0:
            _LOGGER.error("EcoVacsMQTT - error connecting with MQTT Return {}".format(rc))
            raise RuntimeError("EcoVacsMQTT - error connecting with MQTT Return {}".format(rc))
                 
        else:
            #_LOGGER.debug("EcoVacsMQTT - Connected with result code "+str(rc))
            #_LOGGER.debug("EcoVacsMQTT - Subscribing to all")        

            self.subscribe('iot/atr/+/' + self.vacuum['did'] + '/' + self.vacuum['class'] + '/' + self.vacuum['resource'] + '/+', qos=0)            
            self.ready_flag.set()

    def send_ping(self):
        #_LOGGER.debug("*** MQTT sending ping ***")
        rc = self._send_simple_command(MQTTPublish.paho.PINGREQ)
        if rc == MQTTPublish.paho.MQTT_ERR_SUCCESS:
            return True         
        else:
            return False

    def send_command(self, action, recipient):
        if action.name.lower() == 'getcleanlogs':
            
            self._handle_ctl_api(action, self.CallCleanLogsApi(self.jsonRequestHeaderCleanLogs(action, recipient) ,verify_ssl=self.verify_ssl ))
        else:
            self._handle_ctl_api(action, self.CallIOTApi(self.jsonRequestHeader(action, recipient) ,verify_ssl=self.verify_ssl ))

    def jsonRequestHeaderCleanLogs(self, cmd, recipient):
        return {
            'auth': {
                'realm': self.realm,
                'resource': self.resource,
                'token': self.secret,
                'userid': self.user,
                'with': 'users',
            },
            "td": cmd.name,
            "did": recipient,
            "resource": self.vacuum['resource'],
        }     

    def jsonRequestHeader(self, cmd, recipient):
        #All requests need to have this header -- not sure about timezone and ver
        payloadRequest = OrderedDict()
			
        payloadRequest['header'] = OrderedDict()
        payloadRequest['header']['pri'] = '2'
        payloadRequest['header']['ts'] = datetime.datetime.now().timestamp()
        payloadRequest['header']['tmz'] = 480
        payloadRequest['header']['ver'] = '0.0.22'
        
        if len(cmd.args) > 0:
            payloadRequest['body'] = OrderedDict()
            payloadRequest['body']['data'] = cmd.args
			
        payload = payloadRequest
        payloadType = "j"

        return {
            'auth': {
                'realm': self.realm,
                'resource': self.resource,
                'token': self.secret,
                'userid': self.user,
                'with': 'users',
            },
            "cmdName": cmd.name,            
            "payload": payload,  
                      
            "payloadType": payloadType,
            "td": "q",
            "toId": recipient,
            "toRes": self.vacuum['resource'],
            "toType": self.vacuum['class']
        }     

    def CallIOTApi(self, args, verify_ssl=True):
        params = {}
        params.update(args)

        headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)',}
        url = (self.portal_url_format + "/iot/devmanager.do?mid=" + params['toType'] + "&did=" + params['toId'] + "&td=" + params['td'] + "&u=" + params['auth']['userid'] + "&cv=1.67.3&t=a&av=1.3.1").format(continent=self.continent)
        
        try:  
            with requests.post(url, headers=headers, json=params, timeout=20, verify=verify_ssl) as response:
                data = response.json()
                if response.status_code != 200:
                    _LOGGER.warning("Error calling API " + str(url))

                return data
        except:
            return {}
            
    def CallCleanLogsApi(self, args, verify_ssl=True):
        params = {}
        params.update(args)

        headers = {'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)',}
        url = (self.portal_url_format + "/lg/log.do?td=" + params['td'] + "&u=" + params['auth']['userid'] + "&cv=1.67.3&t=a&av=1.3.1").format(continent=self.continent)

        try:
            with requests.post(url, headers=headers, json=params, timeout=20, verify=verify_ssl) as response:
                data = response.json()
                if response.status_code != 200:
                    _LOGGER.warning("Error calling API " + str(url))

                return data
        except:
            return {}

    def _handle_ctl_api(self, action, message):
        if not message == {}:
            if(action.name.lower() == 'getcleanlogs'):
                resp = self._ctl_to_dict_api(action, message)
            else:
                resp = self._ctl_to_dict_api(action, message['resp'])
            if resp is not None:
                for s in self.ctl_subscribers:
                    s(resp)       

    def _ctl_to_dict_api(self, action, jsonstring):
        eventname = action.name.lower()

        if eventname == 'getcleanlogs':
            jsonstring['event'] = "clean_logs"
        elif jsonstring['body']['msg'] == 'ok':
            if 'cleaninfo' in eventname:
                jsonstring['event'] = "clean_report"
            elif 'chargestate' in eventname:
                jsonstring['event'] = "charge_state"
            elif 'battery' in eventname:
                jsonstring['event'] = "battery_info"
            elif 'lifespan' in eventname:
                jsonstring['event'] = "life_span"
            elif 'getspeed' in eventname:
                jsonstring['event'] = "fan_speed"
            elif 'cachedmapinfo' in eventname:
                jsonstring['event'] = "cached_map"
            elif 'minormap' in eventname:
                jsonstring['event'] = "minor_map"
            elif 'majormap' in eventname:
                jsonstring['event'] = "major_map"
            elif 'mapset' in eventname:
                jsonstring['event'] = "map_set"
            elif 'mapsubset' in eventname:
                jsonstring['event'] = "map_sub_set"
            elif 'getwater' in eventname:
                jsonstring['event'] = "water_info"
            elif 'getpos' in eventname:
                jsonstring['event'] = "set_position"
            else:
                # No need to handle other events
                return
        else:
            if jsonstring['body']['msg'] == 'fail':
                if action.name == "charge": #So far only seen this with Charge, when already docked
                    jsonstring['event'] = "charge_state"
                return
            else:
                return

        return jsonstring