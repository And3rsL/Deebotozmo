import datetime
import logging
from typing import Union

import requests

from deebotozmo.commands import Command, GetCleanLogs
from deebotozmo.models import Vacuum

_LOGGER = logging.getLogger(__name__)


class EcovacsJSON:
    REQUEST_HEADERS = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)",
    }

    def __init__(
            self,
            auth: dict,
            portal_url: str,
            verify_ssl: Union[bool, str],
    ):
        self._auth = auth
        self.portal_url = portal_url
        self.verify_ssl = verify_ssl

    def send_command(self, command: Command, vacuum: Vacuum) -> dict:
        json, url = self._get_json_and_url(command, vacuum)

        _LOGGER.debug(f"Calling {url} with {json}")

        response_data = {}
        try:
            with requests.post(
                    url, headers=EcovacsJSON.REQUEST_HEADERS, json=json, timeout=60, verify=self.verify_ssl
            ) as response:
                if response.status_code == 502:
                    _LOGGER.info("Error calling API (502): Unfortunately the ecovacs api is unreliable.")
                    _LOGGER.debug(f"URL was: {str(url)}")
                    return {}
                elif response.status_code != 200:
                    _LOGGER.warning(f"Error calling API ({response.status_code}): {str(url)}")
                    return {}

                response_data = response.json()
                _LOGGER.debug(f"Got {response_data}")
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug("Http Error: " + str(errh))
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug("Error Connecting: " + str(errc))
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug("Timeout Error: " + str(errt))

        return response_data

    def _get_json_and_url(self, command: Command, vacuum: Vacuum) -> (dict, str):
        json = {"auth": self._auth}
        url = self.portal_url

        if command.name == GetCleanLogs().name:
            json.update({
                "td": command.name,
                "did": vacuum.did,
                "resource": vacuum.resource,
            })

            url += f"/lg/log.do?"
        else:
            payload = {
                "header": {
                    "pri": "2",
                    "ts": datetime.datetime.now().timestamp(),
                    "tmz": 480,
                    "ver": "0.0.22"
                }
            }

            if len(command.args) > 0:
                payload["body"] = {
                    "data": command.args
                }

            json.update({
                "cmdName": command.name,
                "payload": payload,
                "payloadType": "j",
                "td": "q",
                "toId": vacuum.did,
                "toRes": vacuum.resource,
                "toType": vacuum.get_class,
            })

            url += f"/iot/devmanager.do?mid={json['toType']}&did={json['toId']}&"

        url += f"td={json.get('td')}&u={json['auth']['userid']}&cv=1.67.3&t=a&av=1.3.1"
        return json, url
