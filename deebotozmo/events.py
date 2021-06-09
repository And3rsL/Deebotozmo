import asyncio
import logging
import time
from asyncio import Task
from dataclasses import dataclass
from typing import List, TypeVar, Generic, Callable, Awaitable, Optional

from deebotozmo.models import Room

_LOGGER = logging.getLogger(__name__)


@dataclass
class StatsEvent:
    area: Optional[int]
    clean_id: Optional[str]
    time: Optional[int]
    type: Optional[str]
    start: Optional[int]


@dataclass
class ErrorEvent:
    code: int
    description: Optional[str]


@dataclass
class FanSpeedEvent:
    speed: str


@dataclass
class BatteryEvent:
    value: int


@dataclass
class StatusEvent:
    available: bool
    state: str


@dataclass
class LifeSpanEvent:
    type: str
    percent: float


@dataclass
class WaterInfoEvent:
    mopAttached: bool
    amount: Optional[str]


@dataclass
class CleanLogEntry:
    timestamp: Optional[int]
    imageUrl: Optional[str]
    type: Optional[str]
    area: Optional[int]
    stopReason: Optional[str]
    # Stop reason
    # 1 -> finished
    # 2 -> manual stopped
    # 3 -> finished with warnings (ex. a scheduled room was not cleaned)
    totalTime: Optional[int]  # in seconds


@dataclass
class CleanLogEvent:
    logs: List[CleanLogEntry]


@dataclass
class RoomsEvent:
    rooms: List[Room]


@dataclass
class MapEvent:
    pass


T = TypeVar('T')


class EventListener(Generic[T]):
    """Object that allows event consumers to easily unsubscribe from events."""

    def __init__(self, emitter: "EventEmitter", callback: Callable[[T], Awaitable[None]]):
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        self._emitter.unsubscribe(self)


class EventEmitter(Generic[T]):
    """A very simple event emitting system."""

    def __init__(self, refresh_function: Callable[[], Awaitable[None]]):
        self._subscribers: List[EventListener] = []
        self._refresh_function: Callable[[], Awaitable[None]] = refresh_function
        self._last_notification_time = None

    @property
    def has_subscribers(self) -> bool:
        return len(self._subscribers) > 0

    def subscribe(self, callback: Callable[[T], Awaitable[None]]) -> EventListener[T]:
        listener = EventListener(self, callback)
        self._subscribers.append(listener)

        if not self._last_notification_time and len(self._subscribers) == 1:
            self.request_refresh()

        return listener

    def unsubscribe(self, listener: EventListener[T]):
        self._subscribers.remove(listener)

    def notify(self, event: T):
        _LOGGER.debug(f"Notify subscriber with {event}")
        self._last_notification_time = time.time()
        for subscriber in self._subscribers:
            asyncio.create_task(subscriber.callback(event))

    def request_refresh(self):
        if len(self._subscribers) > 0:
            asyncio.create_task(self._refresh_function())


class PollingEventEmitter(EventEmitter[T]):

    def __init__(self, refresh_interval: int, refresh_function: Callable[[], Awaitable[None]]):
        super().__init__(refresh_function)
        self._refresh_task: Optional[Task] = None
        self._refresh_interval: int = refresh_interval

    async def _refresh_interval_task(self):
        while True:
            await self._refresh_function()
            await asyncio.sleep(self._refresh_interval)

    def subscribe(self, callback: Callable[[T], Awaitable[None]]) -> EventListener[T]:
        listener = super(PollingEventEmitter, self).subscribe(callback)

        if self._refresh_task is None:
            self._refresh_task = asyncio.create_task(self._refresh_interval_task())

        return listener

    def unsubscribe(self, listener: EventListener[T]):
        super().unsubscribe(listener)

        if len(self._subscribers) == 0 and self._refresh_task is not None:
            task = self._refresh_task
            self._refresh_task = None
            task.cancel()
