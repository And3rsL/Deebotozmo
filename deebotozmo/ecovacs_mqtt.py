import json
import logging
import ssl
from typing import MutableMapping

from gmqtt import Client
from gmqtt.mqtt.constants import MQTTv311

from deebotozmo.models import Vacuum, RequestAuth
from deebotozmo.vacuum_bot import VacuumBot

_LOGGER = logging.getLogger(__name__)

_ON_MESSAGE_RETURN_SUCCESS = 0


def _get_topic(vacuum: Vacuum) -> str:
    return f"iot/atr/+/{vacuum.did}/{vacuum.get_class}/{vacuum.resource}/+"


class EcovacsMqtt:

    def __init__(self, auth: RequestAuth, *, continent: str, country: str):
        self._subscribers: MutableMapping[str, VacuumBot] = {}
        self._port = 443
        self._hostname = f"mq-{continent}.ecouser.net"
        if country.lower() == "cn":
            self._hostname = "mq.ecouser.net"

        client_id = f"{auth.user_id}@ecouser/{auth.resource}"
        self._client = Client(client_id)

        async def _on_message(client, topic: str, payload: bytes, qos, properties) -> int:
            try:
                _LOGGER.debug(f"Got message: topic={topic}; payload={payload};")
                topic_split = topic.split("/")
                if len(topic_split) != 7:
                    _LOGGER.info(f"Unexpected message, skipping... topic={topic}; payload={payload};")
                    return _ON_MESSAGE_RETURN_SUCCESS
                elif topic_split[6] != "j":
                    _LOGGER.warning(
                        f"Received message type was not json, skipping... topic={topic}; payload={payload};")
                    return _ON_MESSAGE_RETURN_SUCCESS

                bot = self._subscribers.get(topic_split[3])
                if bot:
                    data = json.loads(payload)
                    await bot.handle(topic_split[2], data, False)
                return _ON_MESSAGE_RETURN_SUCCESS
            except Exception as err:
                _LOGGER.error("An exception occurred", err, exc_info=True)

        self._client.on_message = _on_message
        self._client.set_auth_credentials(auth.user_id, auth.token)

    async def initialize(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        await self._client.connect(self._hostname, self._port, ssl=ssl_ctx, version=MQTTv311)

    async def subscribe(self, vacuum_bot: VacuumBot):
        if not self._client.is_connected:
            await self.initialize()

        vacuum = vacuum_bot.vacuum
        self._client.subscribe(_get_topic(vacuum))
        self._subscribers[vacuum.did] = vacuum_bot

    def unsubscribe(self, vacuum_bot: VacuumBot):
        vacuum = vacuum_bot.vacuum
        sub = self._subscribers.pop(vacuum.did, None)

        if sub:
            self._client.unsubscribe(_get_topic(vacuum))

    def disconnect(self) -> None:
        self._client.disconnect()
        self._subscribers.clear()
