"""MQTT module."""
import json
import logging
import ssl
from typing import Dict, List, MutableMapping, Optional

from cachetools import TTLCache
from gmqtt import Client, Subscription
from gmqtt.mqtt.constants import MQTTv311

from deebotozmo.commands import COMMANDS, SET_COMMAND_NAMES, SetCommand
from deebotozmo.models import RequestAuth, Vacuum
from deebotozmo.vacuum_bot import VacuumBot

_LOGGER = logging.getLogger(__name__)


def _get_subscriptions(vacuum: Vacuum) -> List[Subscription]:
    return [
        # iot/atr/[command]]/[did]]/[class]]/[resource]/j
        Subscription(f"iot/atr/+/{vacuum.did}/{vacuum.get_class}/{vacuum.resource}/j"),
        # iot/p2p/[command]]/[sender did]/[sender class]]/[sender resource]
        # /[receiver did]/[receiver class]]/[receiver resource]/[q|p/[request id/j
        # [q|p] q-> request p-> response
        Subscription(
            f"iot/p2p/+/+/+/+/{vacuum.did}/{vacuum.get_class}/{vacuum.resource}/q/+/j"
        ),
        Subscription(
            f"iot/p2p/+/{vacuum.did}/{vacuum.get_class}/{vacuum.resource}/+/+/+/p/+/j"
        ),
    ]


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
        self._received_set_commands: MutableMapping[str, SetCommand] = TTLCache(
            maxsize=60 * 60, ttl=60
        )

        # pylint: disable=unused-argument
        async def _on_message(
            client: Client, topic: str, payload: bytes, qos: int, properties: Dict
        ) -> None:
            _LOGGER.debug("Got message: topic=%s; payload=%s;", topic, payload.decode())
            topic_split = topic.split("/")
            if topic.startswith("iot/atr"):
                await self._handle_atr(topic_split, payload)
            elif topic.startswith("iot/p2p"):
                self._handle_p2p(topic_split, payload)
            else:
                _LOGGER.debug("Got unsupported topic: %s", topic)

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
        self._client.subscribe(_get_subscriptions(vacuum))
        self._subscribers[vacuum.did] = vacuum_bot

    def unsubscribe(self, vacuum_bot: VacuumBot) -> None:
        """Unsubscribe given vacuum."""
        vacuum = vacuum_bot.vacuum

        if self._subscribers.pop(vacuum.did, None) and self._client:
            for subscription in _get_subscriptions(vacuum):
                self._client.unsubscribe(subscription.topic)

    def disconnect(self) -> None:
        """Disconnect from MQTT."""
        if self._client:
            self._client.disconnect()
        self._subscribers.clear()

    async def _handle_atr(self, topic_split: List[str], payload: bytes) -> None:
        try:
            bot = self._subscribers.get(topic_split[3])
            if bot:
                data = json.loads(payload)
                await bot.handle(topic_split[2], data, None)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "An exception occurred during handling atr message", exc_info=True
            )

    def _handle_p2p(self, topic_split: List[str], payload: bytes) -> None:
        try:
            command_name = topic_split[2]
            if command_name not in SET_COMMAND_NAMES:
                # command doesn't need special treatment or is not supported yet
                return

            is_request = topic_split[9] == "q"
            request_id = topic_split[10]

            if is_request:
                payload_json = json.loads(payload)
                try:
                    data = payload_json["body"]["data"]
                except KeyError:
                    _LOGGER.warning(
                        "Could not parse p2p payload: topic=%s; payload=%s",
                        "/".join(topic_split),
                        payload_json,
                    )
                    return

                command_class = COMMANDS.get(command_name)
                if command_class and issubclass(command_class, SetCommand):
                    self._received_set_commands[request_id] = command_class(**data)
            else:
                command = self._received_set_commands.get(request_id, None)
                if not command:
                    _LOGGER.debug(
                        "Response to setCommand came in probably to late. requestId=%s, commandName=%s",
                        request_id,
                        command_name,
                    )
                    return

                bot = self._subscribers.get(topic_split[3])
                if bot:
                    data = json.loads(payload)
                    if command.handle(bot.events, data) and isinstance(
                        command.args, dict
                    ):
                        command.get_command.handle(bot.events, command.args)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "An exception occurred during handling p2p message", exc_info=True
            )
