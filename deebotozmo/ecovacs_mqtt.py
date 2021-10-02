"""MQTT module."""
import json
import logging
import ssl
from typing import Dict, MutableMapping, Optional

from gmqtt import Client
from gmqtt.mqtt.constants import MQTTv311

from deebotozmo.models import RequestAuth, Vacuum
from deebotozmo.vacuum_bot import VacuumBot

_LOGGER = logging.getLogger(__name__)


def _get_topic(vacuum: Vacuum) -> str:
    return f"iot/atr/+/{vacuum.did}/{vacuum.get_class}/{vacuum.resource}/+"


class NotInitializedError(Exception):
    """Thrown when not class was not initialized correctly."""


class EcovacsMqtt:
    """Handle mqtt connections."""

    def __init__(self, *, continent: str, country: str):
        self._subscribers: MutableMapping[str, VacuumBot] = {}
        self._port = 443
        self._hostname = f"mq-{continent}.ecouser.net"
        if country.lower() == "cn":
            self._hostname = "mq.ecouser.net"

        self._client: Optional[Client] = None

        # pylint: disable=unused-argument
        async def _on_message(
            client: Client, topic: str, payload: bytes, qos: int, properties: Dict
        ) -> None:
            try:
                payload_str = payload.decode()
                _LOGGER.debug("Got message: topic=%s; payload=%s;", topic, payload_str)
                topic_split = topic.split("/")
                if len(topic_split) != 7:
                    _LOGGER.info(
                        "Unexpected message, skipping... topic=%s; payload=%s;",
                        topic,
                        payload_str,
                    )
                elif topic_split[6] != "j":
                    _LOGGER.warning(
                        "Received message type was not json, skipping... topic=%s; payload=%s;",
                        topic,
                        payload_str,
                    )

                bot = self._subscribers.get(topic_split[3])
                if bot:
                    data = json.loads(payload)
                    await bot.handle(topic_split[2], data, None)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.error("An exception occurred", exc_info=True)

        self.__on_message = _on_message

    async def initialize(self, auth: RequestAuth) -> None:
        """Initialize MQTT."""
        if self._client is not None:
            self.disconnect()

        client_id = f"{auth.user_id}@ecouser/{auth.resource}"
        self._client = Client(client_id)
        self._client.on_message = self.__on_message
        self._client.set_auth_credentials(auth.user_id, auth.token)

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        await self._client.connect(
            self._hostname, self._port, ssl=ssl_ctx, version=MQTTv311
        )

    async def subscribe(self, vacuum_bot: VacuumBot) -> None:
        """Subscribe for messages for given vacuum."""
        if self._client is None:
            raise NotInitializedError

        vacuum = vacuum_bot.vacuum
        self._client.subscribe(_get_topic(vacuum))
        self._subscribers[vacuum.did] = vacuum_bot

    def unsubscribe(self, vacuum_bot: VacuumBot) -> None:
        """Unsubscribe given vacuum."""
        vacuum = vacuum_bot.vacuum
        sub = self._subscribers.pop(vacuum.did, None)

        if sub and self._client:
            self._client.unsubscribe(_get_topic(vacuum))

    def disconnect(self) -> None:
        """Disconnect from MQTT."""
        if self._client:
            self._client.disconnect()
        self._subscribers.clear()
