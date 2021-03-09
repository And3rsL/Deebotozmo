import sched
import time
import threading
import ssl
import datetime
import requests
import logging

from collections import OrderedDict
from threading import Event

_LOGGER = logging.getLogger(__name__)


def str_to_bool_or_cert(s):
    if s == "True" or s == True:
        return True
    elif s == "False" or s == False:
        return False
    else:
        if not s == None:
            if os.path.exists(
                s
            ):  # User could provide a path to a CA Cert as well, which is useful for Bumper
                if os.path.isfile(s):
                    return s
                else:
                    raise ValueError(
                        "Certificate path provided is not a file - {}".format(s)
                    )

        raise ValueError("Cannot covert {} to a bool or certificate path".format(s))


class EcoVacsJSON:
    def __init__(
        self,
        user,
        resource,
        secret,
        continent,
        vacuum,
        realm,
        portal_url_format,
        verify_ssl=True,
    ):
        self.ctl_subscribers = []
        self.user = user
        self.resource = resource
        self.secret = secret
        self.continent = continent
        self.vacuum = vacuum
        self.scheduler = sched.scheduler(time.time, time.sleep)

        self.scheduler_thread = threading.Thread(
            target=self.scheduler.run, daemon=True, name="schedule_thread"
        )

        self.schedulerLV = sched.scheduler(time.time, time.sleep)
        self.scheduler_LiveMap = threading.Thread(
            target=self.schedulerLV.run, daemon=True, name="schedule_livemap"
        )

        self.verify_ssl = str_to_bool_or_cert(verify_ssl)
        self.realm = realm
        self.portal_url_format = portal_url_format

    def subscribe_to_ctls(self, function):
        self.ctl_subscribers.append(function)

    def _disconnect(self):
        self.scheduler.empty()  # Clear schedule queue

    # Schedule Thread
    def _run_scheduled_func(self, timer_seconds, timer_function):
        timer_function()
        self.schedule(timer_seconds, timer_function)

    def schedule(self, timer_seconds, timer_function):
        self.scheduler.enter(
            timer_seconds, 1, self._run_scheduled_func, (timer_seconds, timer_function)
        )
        if not self.scheduler_thread.is_alive():
            self.scheduler_thread.start()

    # Schedule Live Map
    def _run_scheduled_LiveMap_func(self, timer_seconds, timer_function):
        timer_function()
        self.scheduleLiveMap(timer_seconds, timer_function)

    def scheduleLiveMap(self, timer_seconds, timer_function):
        self.schedulerLV.enter(
            timer_seconds,
            1,
            self._run_scheduled_LiveMap_func,
            (timer_seconds, timer_function),
        )

        if not self.scheduler_LiveMap.is_alive():
            self.scheduler_LiveMap.start()

    def send_command(self, action, recipient):
        if action.name.lower() == "getcleanlogs":

            self._handle_ctl_api(
                action,
                self.CallCleanLogsApi(
                    self.jsonRequestHeaderCleanLogs(action, recipient),
                    verify_ssl=self.verify_ssl,
                ),
            )
        else:
            self._handle_ctl_api(
                action,
                self.CallIOTApi(
                    self.jsonRequestHeader(action, recipient),
                    verify_ssl=self.verify_ssl,
                ),
            )

    def jsonRequestHeaderCleanLogs(self, cmd, recipient):
        return {
            "auth": {
                "realm": self.realm,
                "resource": self.resource,
                "token": self.secret,
                "userid": self.user,
                "with": "users",
            },
            "td": cmd.name,
            "did": recipient,
            "resource": self.vacuum["resource"],
        }

    def jsonRequestHeader(self, cmd, recipient):
        # All requests need to have this header -- not sure about timezone and ver
        payloadRequest = OrderedDict()

        payloadRequest["header"] = OrderedDict()
        payloadRequest["header"]["pri"] = "2"
        payloadRequest["header"]["ts"] = datetime.datetime.now().timestamp()
        payloadRequest["header"]["tmz"] = 480
        payloadRequest["header"]["ver"] = "0.0.22"

        if len(cmd.args) > 0:
            payloadRequest["body"] = OrderedDict()
            payloadRequest["body"]["data"] = cmd.args

        payload = payloadRequest
        payloadType = "j"

        return {
            "auth": {
                "realm": self.realm,
                "resource": self.resource,
                "token": self.secret,
                "userid": self.user,
                "with": "users",
            },
            "cmdName": cmd.name,
            "payload": payload,
            "payloadType": payloadType,
            "td": "q",
            "toId": recipient,
            "toRes": self.vacuum["resource"],
            "toType": self.vacuum["class"],
        }

    def CallIOTApi(self, args, verify_ssl=True):
        params = {}
        params.update(args)

        # _LOGGER.debug(f"Calling IOT api with {args}")

        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)",
        }
        url = (
            self.portal_url_format
            + "/iot/devmanager.do?mid="
            + params["toType"]
            + "&did="
            + params["toId"]
            + "&td="
            + params["td"]
            + "&u="
            + params["auth"]["userid"]
            + "&cv=1.67.3&t=a&av=1.3.1"
        ).format(continent=self.continent)

        try:
            with requests.post(
                url, headers=headers, json=params, timeout=60, verify=verify_ssl
            ) as response:
                if response.status_code == 502:
                    # _LOGGER.info("Error calling API (502): Unfortunately the ecovacs api is unreliable. Retrying in a few moments")
                    # _LOGGER.debug(f"URL was: {str(url)}")
                    return {}
                elif response.status_code != 200:
                    # _LOGGER.warning(f"Error calling API ({response.status_code}): {str(url)}")
                    return {}

                data = response.json()
                # _LOGGER.debug(f"Got {data}")

                return data
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug("Http Error: " + str(errh))
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug("Error Connecting: " + str(errc))
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug("Timeout Error: " + str(errt))

    def CallCleanLogsApi(self, args, verify_ssl=True):
        params = {}
        params.update(args)

        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)",
        }
        url = (
            self.portal_url_format
            + "/lg/log.do?td="
            + params["td"]
            + "&u="
            + params["auth"]["userid"]
            + "&cv=1.67.3&t=a&av=1.3.1"
        ).format(continent=self.continent)

        try:
            with requests.post(
                url, headers=headers, json=params, timeout=60, verify=verify_ssl
            ) as response:
                data = response.json()
                if response.status_code != 200:
                    _LOGGER.warning("Error calling API " + str(url))

                return data
        except:
            return {}

    def _handle_ctl_api(self, action, message):
        eventname = action.name.lower()

        if message is not None:
            if eventname == "getcleanlogs":
                resp = self._ctl_to_dict_api(eventname, message)
            else:
                resp = self._ctl_to_dict_api(eventname, message.get("resp"))

            if resp is not None:
                for s in self.ctl_subscribers:
                    s(resp)

    def _ctl_to_dict_api(self, eventname: str, jsonstring: dict):
        if jsonstring is None or jsonstring == {}:
            return

        if eventname == "getcleanlogs":
            jsonstring["event"] = "clean_logs"
        elif jsonstring["body"]["msg"] == "ok":
            if "cleaninfo" in eventname:
                jsonstring["event"] = "clean_report"
            elif "chargestate" in eventname:
                jsonstring["event"] = "charge_state"
            elif "battery" in eventname:
                jsonstring["event"] = "battery_info"
            elif "lifespan" in eventname:
                jsonstring["event"] = "life_span"
            elif "getspeed" in eventname:
                jsonstring["event"] = "fan_speed"
            elif "cachedmapinfo" in eventname:
                jsonstring["event"] = "cached_map"
            elif "minormap" in eventname:
                jsonstring["event"] = "minor_map"
            elif "majormap" in eventname:
                jsonstring["event"] = "major_map"
            elif "mapset" in eventname:
                jsonstring["event"] = "map_set"
            elif "mapsubset" in eventname:
                jsonstring["event"] = "map_sub_set"
            elif "getwater" in eventname:
                jsonstring["event"] = "water_info"
            elif "getpos" in eventname:
                jsonstring["event"] = "set_position"
            elif "getmaptrace" in eventname:
                jsonstring["event"] = "map_trace"
            elif "getstats" in eventname:
                jsonstring["event"] = "stats"
            else:
                # No need to handle other events
                return
        else:
            if jsonstring["body"]["msg"] == "fail":
                if (
                    eventname == "charge"
                ):  # So far only seen this with Charge, when already docked
                    jsonstring["event"] = "charge_state"
                return
            else:
                return

        return jsonstring
