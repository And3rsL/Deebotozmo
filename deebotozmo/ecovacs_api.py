import logging
import time
from typing import Union, Optional, List

import requests
import urllib3

from deebotozmo.models import Vacuum
from deebotozmo.util import str_to_bool_or_cert, md5

_LOGGER = logging.getLogger(__name__)


class EcovacsAPI:
    CLIENT_KEY = "1520391301804"
    CLIENT_SECRET = "6c319b2a5cd3e66e39159c2e28f2fce9"
    MAIN_URL_FORMAT = "https://gl-{country}-api.ecovacs.com/v1/private/{country}/{lang}/{deviceId}/{appCode}/{appVersion}/{channel}/{deviceType}"
    USER_URL_FORMAT = "https://users-{continent}.ecouser.net:8000/user.do"
    PORTAL_URL_FORMAT = "https://portal-{continent}.ecouser.net/api"
    PORTAL_URL_FORMAT_CN = "https://portal.ecouser.net/api/"

    # New Auth Code Method
    PORTAL_GLOBAL_AUTHCODE = "https://gl-{country}-openapi.ecovacs.com/v1/global/auth/getAuthCode"
    AUTH_CLIENT_KEY = "1520391491841"
    AUTH_CLIENT_SECRET = "77ef58ce3afbe337da74aa8c5ab963a9"

    API_USERS_USER = "users/user.do"
    API_IOT_DEVMANAGER = "iot/devmanager.do"  # IOT Device Manager - This provides control of "IOT" products via RestAPI
    API_PIM_PRODUCT = "pim/product"  # Leaving this open, the only endpoint known currently is "Product IOT Map" -  pim/product/getProductIotMap - This provides a list of "IOT" products.  Not sure what this provides the app.
    API_APPSVR_APP = "appsvr/app.do"
    REALM = "ecouser.net"
    META = {
        "lang": "EN",
        "appCode": "global_e",
        "appVersion": "1.6.3",
        "channel": "google_play",
        "deviceType": "1",
    }

    def __init__(
            self, device_id, account_id, password_hash, country, continent, verify_ssl: Union[bool, str] = True
    ):
        self.meta = {**EcovacsAPI.META,
                     "country": country,
                     "deviceId": device_id,
                     }

        if verify_ssl is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.verify_ssl = str_to_bool_or_cert(verify_ssl)

        _LOGGER.debug("Setting up EcovacsAPI")
        self.resource = device_id[0:8]
        self.country = country
        self.continent = continent

        login_info = self.__call_login_api(account_id, password_hash)
        self.uid = login_info["uid"]

        self.auth_code = self.__call_auth_api(login_info["accessToken"])

        login_response = self.__call_login_by_it_token()
        self.user_access_token = login_response["token"]
        if login_response["userId"] != self.uid:
            _LOGGER.debug("Switching to shorter UID " + login_response["userId"])
            self.uid = login_response["userId"]
        _LOGGER.debug("EcovacsAPI connection complete")

    @staticmethod
    def __get_signed_md5(data: dict, key: str, secret: str) -> str:
        sign_on_text = (
                key
                + "".join([k + "=" + str(data[k]) for k in sorted(data.keys())])
                + secret
        )
        return md5(sign_on_text)

    def __sign(self, params):
        result = {**params, "authTimespan": int(time.time() * 1000), "authTimeZone": "GMT-8"}
        sign_data = {**self.meta, **result}
        result["authSign"] = self.__get_signed_md5(sign_data, EcovacsAPI.CLIENT_KEY, EcovacsAPI.CLIENT_SECRET)
        result["authAppkey"] = EcovacsAPI.CLIENT_KEY
        return result

    def __sign_auth(self, params: dict) -> dict:
        result = {**params, "authTimespan": int(time.time() * 1000)}
        sign_data = {**result, "openId": "global"}
        result["authSign"] = self.__get_signed_md5(sign_data, EcovacsAPI.AUTH_CLIENT_KEY, EcovacsAPI.AUTH_CLIENT_SECRET)
        result["authAppkey"] = EcovacsAPI.AUTH_CLIENT_KEY
        return result

    def __do_auth_response(self, url: str, data: dict) -> dict:
        if self.country.lower() == "cn":
            url = url.replace(".ecovacs.com", ".ecovacs.cn")

        api_response = requests.get(url, data, timeout=60, verify=self.verify_ssl)

        json = api_response.json()
        _LOGGER.debug(f"got {json}")
        if json["code"] == "0000":
            return json["data"]
        elif json["code"] == "1005":
            _LOGGER.warning("incorrect email or password")
            raise ValueError("incorrect email or password")
        else:
            _LOGGER.error(f"call to {url} failed with {json}")
            raise RuntimeError(f"failure code {json['code']} ({json['msg']}) for call {url}")

    def __call_login_api(self, account_id: str, password_hash: str):
        _LOGGER.debug(f"calling login api")
        params = {
            "account": account_id,
            "password": password_hash,
            "requestId": md5(time.time())
        }

        url = (EcovacsAPI.MAIN_URL_FORMAT + "/user/login").format(**self.meta)

        return self.__do_auth_response(url, self.__sign(params))

    def __call_auth_api(self, access_token: str):
        _LOGGER.debug(f"calling auth api")
        params = {
            "uid": self.uid,
            "accessToken": access_token,
            "bizType": "ECOVACS_IOT",
            "deviceId": self.meta["deviceId"]
        }

        url = EcovacsAPI.PORTAL_GLOBAL_AUTHCODE.format(**self.meta)

        return self.__do_auth_response(url, self.__sign_auth(params))["authCode"]

    def __call_portal_api(self, api: str, args: dict, continent: Optional[str] = None):
        _LOGGER.debug(f"calling user api {api} with {args}")
        params = {**args}

        base_url = EcovacsAPI.PORTAL_URL_FORMAT
        if self.country.lower() == "cn":
            base_url = EcovacsAPI.PORTAL_URL_FORMAT

        format_data = {**self.meta, "continent": self.continent}
        if continent is not None:
            format_data["continent"] = continent

        url = (base_url + "/" + api).format(**format_data)

        response = requests.post(url, json=params, timeout=60, verify=self.verify_ssl)

        json = response.json()
        _LOGGER.debug("got {}".format(json))
        return json

    def __call_login_by_it_token(self):
        data = {
            "edition": "ECOGLOBLE",
            "userId": self.uid,
            "token": self.auth_code,
            "realm": EcovacsAPI.REALM,
            "resource": self.resource,
            "org": "ECOWW",
            "last": "",
            "country": self.meta["country"].upper(),
            "todo": "loginByItToken"
        }

        if self.country.lower() == "cn":
            data.update({
                "org": "ECOCN",
                "country": "Chinese"
            })

        for c in range(3):
            json = self.__call_portal_api(self.API_USERS_USER, data)
            if json["result"] == "ok":
                return json
            elif json["result"] == "fail":
                if c == 2:
                    _LOGGER.warning("loginByItToken set token error, failed after 3 attempts")
                elif json["error"] == "set token error.":  # If it is a set token error try again
                    _LOGGER.warning(f"loginByItToken set token error, trying again ({c + 2}/3)")
                    continue

            _LOGGER.error(f"call to {self.API_USERS_USER} failed with {json}")
            raise RuntimeError(
                f"failure {json['error']} ({json['errno']}) for call {self.API_USERS_USER} and parameters {data}")

    def get_request_auth(self) -> dict:
        return {
            "with": "users",
            "userid": self.uid,
            "realm": EcovacsAPI.REALM,
            "token": self.user_access_token,
            "resource": self.resource,
        }

    def get_devices(self) -> List[Vacuum]:
        data = {
            "userid": self.uid,
            "auth": self.get_request_auth(),
            "todo": "GetGlobalDeviceList"
        }
        json = self.__call_portal_api(self.API_APPSVR_APP, data)

        if json["code"] == 0:
            devices: List[Vacuum] = []
            for device in json["devices"]:
                devices.append(Vacuum(device))
            return devices
        else:
            _LOGGER.error(f"call to {self.API_APPSVR_APP} failed with {json}")
            raise RuntimeError(
                f"failure {json['error']} ({json['errno']}) for call {self.API_APPSVR_APP} and parameters {data}")

    def get_product_iot_map(self) -> List[dict]:
        data = {
            "channel": "",
            "auth": self.get_request_auth(),
        }
        api = self.API_PIM_PRODUCT + "/getProductIotMap"
        json = self.__call_portal_api(api, data)

        if json["code"] == "0000":
            return json["data"]
        else:
            _LOGGER.error(f"call to {api} failed with {json}")
            raise RuntimeError(
                f"failure {json['error']} ({json['errno']}) for call {api} and parameters {data}")
