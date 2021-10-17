"""Event emitter module."""
import asyncio
import logging
import threading
from typing import (
    Awaitable,
    Callable,
    Dict,
    Final,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
)

from deebotozmo.commands._base import Command

from . import EventDto

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=EventDto)


class EventListener(Generic[T]):
    """Object that allows event consumers to easily unsubscribe from event bus."""

    def __init__(
        self,
        event_bus: "EventBus",
        event_class: Type[T],
        callback: Callable[[T], Awaitable[None]],
    ) -> None:
        self._event_bus: Final = event_bus
        self._event_class: Final = event_class
        self.callback: Final = callback

    def unsubscribe(self) -> None:
        """Unsubscribe from event bus."""
        self._event_bus.unsubscribe(self._event_class, self)


class _EventProcessingData(Generic[T]):
    """Data class, which holds all needed data per EventDto."""

    def __init__(self) -> None:
        super().__init__()

        self._subscribers: Final[List[EventListener[T]]] = []
        self._semaphore: Final = asyncio.Semaphore(1)
        self.last_event: Optional[T] = None

    @property
    def subscribers(self) -> List[EventListener[T]]:
        """Return subscribers."""
        return self._subscribers

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Return semaphore."""
        return self._semaphore


class EventBus:
    """A very simple event bus system."""

    def __init__(self, execute_command: Callable[[Command], Awaitable[None]]):
        self._event_processing_dict: Dict[Type[EventDto], _EventProcessingData] = {}
        self._lock = threading.Lock()
        self._execute_command: Final = execute_command

    def has_subscribers(self, event: Type[EventDto]) -> bool:
        """Return True, if emitter has subscribers."""
        return (
            len(self._event_processing_dict[event].subscribers) > 0
            if event in self._event_processing_dict
            else False
        )

    def subscribe(
        self,
        event_class: Type[T],
        callback: Callable[[T], Awaitable[None]],
    ) -> EventListener[T]:
        """Subscribe to event."""
        event_processing_data = self._get_or_create_event_processing_data(event_class)

        listener = EventListener(self, event_class, callback)
        event_processing_data.subscribers.append(listener)

        if event_processing_data.last_event:
            # Notify subscriber directly with the last event
            asyncio.create_task(listener.callback(event_processing_data.last_event))
        elif len(event_processing_data.subscribers) == 1:
            # first subscriber therefore do refresh
            self.request_refresh(event_class)

        return listener

    def unsubscribe(
        self, event_class: Type[EventDto], listener: EventListener[T]
    ) -> None:
        """Unsubscribe from event."""
        self._event_processing_dict[event_class].subscribers.remove(listener)

    def notify(self, event: T) -> bool:
        """Notify subscriber with given event representation."""
        event_processing_data = self._get_or_create_event_processing_data(type(event))
        if event == event_processing_data.last_event:
            _LOGGER.debug("Event is the same! Skipping (%s)", event)
            return False

        event_processing_data.last_event = event
        if event_processing_data.subscribers:
            _LOGGER.debug("Notify subscribers with %s", event)
            for subscriber in event_processing_data.subscribers:
                asyncio.create_task(subscriber.callback(event))
            return True

        _LOGGER.debug("No subscribers... Discharging %s", event)
        return False

    def request_refresh(self, event_class: Type[T]) -> None:
        """Request manual refresh."""
        if self.has_subscribers(event_class):
            asyncio.create_task(self._call_refresh_function(event_class))

    async def _call_refresh_function(self, event_class: Type[T]) -> None:
        semaphore = self._event_processing_dict[event_class].semaphore
        if semaphore.locked():
            _LOGGER.debug("Already refresh function running. Skipping...")
            return

        async with semaphore:
            from deebotozmo.events.const import (  # pylint: disable=import-outside-toplevel
                EVENT_DTO_REFRESH_COMMANDS,
            )

            commands = EVENT_DTO_REFRESH_COMMANDS.get(event_class, [])
            if not commands:
                return

            if len(commands) == 1:
                await self._execute_command(commands[0])
            else:
                tasks = []
                for command in commands:
                    tasks.append(asyncio.create_task(self._execute_command(command)))

                await asyncio.gather(*tasks)

    def _get_or_create_event_processing_data(
        self, event_class: Type[T]
    ) -> _EventProcessingData[T]:
        with self._lock:
            event_processing_data = self._event_processing_dict.get(event_class, None)

            if event_processing_data is None:
                event_processing_data = _EventProcessingData()
                self._event_processing_dict[event_class] = event_processing_data

            return event_processing_data
