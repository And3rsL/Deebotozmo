"""API module."""
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import hdrs

from deebotozmo.models import RequestAuth, Vacuum
from deebotozmo.util import md5, sanitize_data, str_to_bool_or_cert

_LOGGER = logging.getLogger(__name__)


class EcovacsAPI:
    """Api representation."""

    CLIENT_KEY = "1520391301804"
    CLIENT_SECRET = "6c319b2a5cd3e66e39159c2e28f2fce9"
    MAIN_URL_FORMAT = (
        "https://gl-{country}-api.ecovacs.com/v1/private/{country}/{lang}/{deviceId}/{appCode}/"
        "{appVersion}/{channel}/{deviceType}"
    )
    USER_URL_FORMAT = "https://users-{continent}.ecouser.net:8000/user.do"
    PORTAL_URL_FORMAT = "https://portal-{continent}.ecouser.net/api"
    PORTAL_URL_FORMAT_CN = "https://portal.ecouser.net/api/"

    # New Auth Code Method
    PORTAL_GLOBAL_AUTHCODE = (
        "https://gl-{country}-openapi.ecovacs.com/v1/global/auth/getAuthCode"
    )
    AUTH_CLIENT_KEY = "1520391491841"
    AUTH_CLIENT_SECRET = "77ef58ce3afbe337da74aa8c5ab963a9"

    API_USERS_USER = "users/user.do"
    API_IOT_DEVMANAGER = "iot/devmanager.do"  # IOT Device Manager - This provides control of "IOT" products via RestAPI
    # Leaving this open, the only endpoint known currently is "Product IOT Map" -  pim/product/getProductIotMap -
    API_PIM_PRODUCT = "pim/product"
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
        self,
        session: aiohttp.ClientSession,
        device_id: str,
        account_id: str,
        password_hash: str,
        *,
        continent: str,
        country: str,
        verify_ssl: Union[bool, str] = True,
    ):
        self._meta: Dict[str, str] = {
            **EcovacsAPI.META,
            "country": country,
            "deviceId": device_id,
        }

        self._session = session
        self._verify_ssl = str_to_bool_or_cert(verify_ssl)

        self._resource = device_id
        self._country = country
        self._continent = continent

        self._account_id = account_id
        self._password_hash = password_hash
        self._login_information: Optional[EcovacsAPI.LoginInformation] = None

    async def login(self) -> None:
        """Login using username and password."""
        _LOGGER.debug("Start login to EcovacsAPI")
        login_info = await self.__call_login_api(self._account_id, self._password_hash)
        user_id = login_info["uid"]

        auth_code = await self.__call_auth_api(login_info["accessToken"], user_id)

        login_response = await self.__call_login_by_it_token(user_id, auth_code)
        user_access_token = login_response["token"]
        if login_response["userId"] != user_id:
            _LOGGER.debug("Switching to shorter UID")
            user_id = login_response["userId"]

        self._login_information = EcovacsAPI.LoginInformation(
            user_access_token, user_id
        )
        _LOGGER.debug("Login to EcovacsAPI successfully")

    async def get_request_auth(self) -> RequestAuth:
        """Return request authentication object for further calls."""
        if self._login_information is None:
            await self.login()
            if self._login_information is None:
                raise RuntimeError("Internal error! Please contact developers.")

        return RequestAuth(
            self._login_information.user_id,
            EcovacsAPI.REALM,
            self._login_information.access_token,
            self._resource,
        )

    async def get_devices(self) -> List[Vacuum]:
        """Get compatible devices."""
        auth_ = await self.get_request_auth()
        data = {
            "userid": auth_.user_id,
            "auth": auth_.to_dict(),
            "todo": "GetGlobalDeviceList",
        }
        json = await self.__call_portal_api(self.API_APPSVR_APP, data)

        if json["code"] == 0:
            devices: List[Vacuum] = []
            for device in json["devices"]:
                if device.get("company") == "eco-ng":
                    devices.append(Vacuum(device))
                else:
                    _LOGGER.debug("Skipping device as it is not supported: %s", device)
            return devices
        _LOGGER.error("call to %s failed with %s", self.API_APPSVR_APP, json)
        raise RuntimeError(
            f"failure {json['error']} ({json['errno']}) for call {self.API_APPSVR_APP} and "
            f"parameters {sanitize_data(data)}"
        )

    async def get_product_iot_map(self) -> List[Dict[str, Any]]:
        """Get product iot map."""
        data = {
            "channel": "",
            "auth": (await self.get_request_auth()).to_dict(),
        }
        api = self.API_PIM_PRODUCT + "/getProductIotMap"
        json = await self.__call_portal_api(api, data)

        if json["code"] == "0000":
            result: List[Dict[str, Any]] = json["data"]
            return result
        _LOGGER.error("call to %s failed with %s", api, json)
        raise RuntimeError(
            f"failure {json['error']} ({json['errno']}) for call {api} and parameters {sanitize_data(data)}"
        )

    @staticmethod
    def __get_signed_md5(
        data: Dict[str, Union[str, int]], key: str, secret: str
    ) -> str:
        sign_on_text = (
            key
            + "".join([k + "=" + str(data[k]) for k in sorted(data.keys())])
            + secret
        )
        return md5(sign_on_text)

    def __sign(self, params: Dict[str, str]) -> Dict[str, Union[str, int]]:
        result: Dict[str, Union[str, int]] = {
            **params,
            "authTimespan": int(time.time() * 1000),
            "authTimeZone": "GMT-8",
        }
        sign_data: Dict[str, Union[str, int]] = {**self._meta, **result}
        result["authSign"] = self.__get_signed_md5(
            sign_data, EcovacsAPI.CLIENT_KEY, EcovacsAPI.CLIENT_SECRET
        )
        result["authAppkey"] = EcovacsAPI.CLIENT_KEY
        return result

    def __sign_auth(self, params: Dict[str, str]) -> Dict[str, Union[str, int]]:
        result: Dict[str, Union[str, int]] = {
            **params,
            "authTimespan": int(time.time() * 1000),
        }
        sign_data: Dict[str, Union[str, int]] = {**result, "openId": "global"}
        result["authSign"] = self.__get_signed_md5(
            sign_data, EcovacsAPI.AUTH_CLIENT_KEY, EcovacsAPI.AUTH_CLIENT_SECRET
        )
        result["authAppkey"] = EcovacsAPI.AUTH_CLIENT_KEY
        return result

    async def __do_auth_response(
        self, url: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self._country.lower() == "cn":
            url = url.replace(".ecovacs.com", ".ecovacs.cn")

        async with self._session.get(
            url, params=params, timeout=60, ssl=self._verify_ssl
        ) as res:
            res.raise_for_status()

            # ecovacs returns a json but content_type header is set to text
            content_type = res.headers.get(hdrs.CONTENT_TYPE, "").lower()
            json = await res.json(content_type=content_type)
            _LOGGER.debug("got %s", json)
            # todo better error handling # pylint: disable=fixme
            if json["code"] == "0000":
                data: Dict[str, Any] = json["data"]
                return data
            if json["code"] == "1005":
                _LOGGER.warning("incorrect email or password")
                raise ValueError("incorrect email or password")

            _LOGGER.error("call to %s failed with %s", url, json)
            raise RuntimeError(
                f"failure code {json['code']} ({json['msg']}) for call {url}"
            )

    async def __call_login_api(
        self, account_id: str, password_hash: str
    ) -> Dict[str, Any]:
        _LOGGER.debug("calling login api")
        params = {
            "account": account_id,
            "password": password_hash,
            "requestId": md5(str(time.time())),
        }

        url = (EcovacsAPI.MAIN_URL_FORMAT + "/user/login").format(**self._meta)

        if self._country.lower() == "cn":
            url += "CheckMobile"

        return await self.__do_auth_response(url, self.__sign(params))

    async def __call_auth_api(self, access_token: str, user_id: str) -> str:
        _LOGGER.debug("calling auth api")
        params = {
            "uid": user_id,
            "accessToken": access_token,
            "bizType": "ECOVACS_IOT",
            "deviceId": self._meta["deviceId"],
        }

        url = EcovacsAPI.PORTAL_GLOBAL_AUTHCODE.format(**self._meta)

        res = await self.__do_auth_response(url, self.__sign_auth(params))
        return str(res["authCode"])

    async def __call_portal_api(
        self, api: str, args: dict, continent: Optional[str] = None
    ) -> Dict[str, Any]:
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("calling user api %s with %s", api, sanitize_data(args))
        params = {**args}

        base_url = EcovacsAPI.PORTAL_URL_FORMAT
        if self._country.lower() == "cn":
            base_url = EcovacsAPI.PORTAL_URL_FORMAT_CN

        format_data = {**self._meta, "continent": self._continent}
        if continent is not None:
            format_data["continent"] = continent

        url = (base_url + "/" + api).format(**format_data)

        async with self._session.post(
            url, json=params, timeout=60, ssl=self._verify_ssl
        ) as res:
            res.raise_for_status()

            json: Dict[str, Any] = await res.json()
            _LOGGER.debug("got %s", json)
            return json

    async def __call_login_by_it_token(
        self, user_id: str, auth_code: str
    ) -> Dict[str, str]:
        data = {
            "edition": "ECOGLOBLE",
            "userId": user_id,
            "token": auth_code,
            "realm": EcovacsAPI.REALM,
            "resource": self._resource,
            "org": "ECOWW",
            "last": "",
            "country": self._meta["country"].upper(),
            "todo": "loginByItToken",
        }

        if self._country.lower() == "cn":
            data.update({"org": "ECOCN", "country": "Chinese"})

        for i in range(3):
            json = await self.__call_portal_api(self.API_USERS_USER, data)
            if json["result"] == "ok":
                return json
            if json["result"] == "fail":
                if i == 2:
                    _LOGGER.warning(
                        "loginByItToken set token error, failed after 3 attempts"
                    )
                elif json["error"] == "set token error.":
                    # If it is a set token error try again
                    _LOGGER.warning(
                        "loginByItToken set token error, trying again (%d/3)", i + 2
                    )
                    continue

            _LOGGER.error("call to %s failed with %s", self.API_USERS_USER, json)
            raise RuntimeError(
                f"failure {json['error']} ({json['errno']}) for call {self.API_USERS_USER} and "
                f"parameters {sanitize_data(data)}"
            )

        raise RuntimeError(
            f"failure for call {self.API_USERS_USER} with parameters {sanitize_data(data)}"
        )

    @dataclass
    class LoginInformation:
        """Private class to store login information, which are later required."""

        access_token: str
        user_id: str
