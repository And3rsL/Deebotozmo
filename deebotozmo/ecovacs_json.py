"""Handles Ecovacs JSON API."""

import datetime
import logging
from typing import Any, Dict, Tuple, Union

import aiohttp
from aiohttp import ClientResponseError

from deebotozmo.commands import Command
from deebotozmo.commands_old import Command as OldCommand
from deebotozmo.commands_old import GetCleanLogs
from deebotozmo.models import RequestAuth, Vacuum
from deebotozmo.util import sanitize_data

_LOGGER = logging.getLogger(__name__)


class EcovacsJSON:
    """Ecovacs json api reppresentation."""

    REQUEST_HEADERS = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)",
    }

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: RequestAuth,
        portal_url: str,
        verify_ssl: Union[bool, str],
    ):
        self._session = session
        self._auth = auth
        self.portal_url = portal_url
        self.verify_ssl = verify_ssl

    async def send_command(
        self, command: Union[Command, OldCommand], vacuum: Vacuum
    ) -> dict:
        """Send json command for given vacuum to the api."""
        json, base_url, url_with_params = self._get_json_and_url(command, vacuum)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Calling %s with %s", base_url, sanitize_data(json))

        try:
            async with self._session.post(
                url_with_params,
                headers=EcovacsJSON.REQUEST_HEADERS,
                json=json,
                timeout=60,
                ssl=self.verify_ssl,
            ) as res:
                res.raise_for_status()
                if res.status != 200:
                    _LOGGER.warning("Error calling API (%d): %s", res.status, base_url)
                    return {}

                json = await res.json()
                _LOGGER.debug("Got %s", json)
                return json
        except ClientResponseError as err:
            if err.status == 502:
                _LOGGER.info(
                    "Error calling API (502): Unfortunately the ecovacs api is unreliable. URL was: %s",
                    base_url,
                )
            else:
                _LOGGER.warning("Error calling API (%sd): %s", err.status, base_url)

        return {}

    def _get_json_and_url(
        self, command: Union[Command, OldCommand], vacuum: Vacuum
    ) -> Tuple[Dict[str, Any], str, str]:
        json: Dict[str, Any] = {"auth": self._auth.to_dict()}
        base_url = self.portal_url
        params = "?"

        if command.name == GetCleanLogs().name:
            json.update(
                {
                    "td": command.name,
                    "did": vacuum.did,
                    "resource": vacuum.resource,
                }
            )

            base_url += "/lg/log.do"
        else:
            payload = {
                "header": {
                    "pri": "1",
                    "ts": datetime.datetime.now().timestamp(),
                    "tzm": 480,
                    "ver": "0.0.50",
                }
            }

            if len(command.args) > 0:
                payload["body"] = {"data": command.args}

            json.update(
                {
                    "cmdName": command.name,
                    "payload": payload,
                    "payloadType": "j",
                    "td": "q",
                    "toId": vacuum.did,
                    "toRes": vacuum.resource,
                    "toType": vacuum.get_class,
                }
            )

            base_url += "/iot/devmanager.do"
            params += "mid={json['toType']}&did={json['toId']}&"

        params += (
            f"td={json.get('td')}&u={json['auth']['userid']}&cv=1.67.3&t=a&av=1.3.1"
        )
        return json, base_url, base_url + params
