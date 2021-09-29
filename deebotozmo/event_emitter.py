"""Event emitter module."""
import asyncio
import logging
import time
from asyncio import Task
from typing import Awaitable, Callable, Final, Generic, List, Optional, TypeVar

from deebotozmo.events import StatusEvent
from deebotozmo.models import VacuumState

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class EventListener(Generic[T]):
    """Object that allows event consumers to easily unsubscribe from events."""

    def __init__(
        self, emitter: "EventEmitter", callback: Callable[[T], Awaitable[None]]
    ) -> None:
        self._emitter: Final = emitter
        self.callback: Final = callback

    def unsubscribe(self) -> None:
        """Unsubscribe from event representation."""
        self._emitter.unsubscribe(self)


class EventEmitter(Generic[T]):
    """A very simple event emitting system."""

    def __init__(
        self,
        refresh_function: Callable[[], Awaitable[None]],
        notify_on_equal_event: bool = False,
    ):
        self._subscribers: List[EventListener] = []
        self._refresh_function: Callable[[], Awaitable[None]] = refresh_function
        self._semaphore = asyncio.Semaphore(1)
        self._last_event: Optional[T] = None
        self._notify_on_equal_event = notify_on_equal_event

    @property
    def has_subscribers(self) -> bool:
        """Return True, if emitter has subscribers."""
        return len(self._subscribers) > 0

    def subscribe(self, callback: Callable[[T], Awaitable[None]]) -> EventListener[T]:
        """Subscribe to event."""
        listener = EventListener(self, callback)
        self._subscribers.append(listener)

        if self._last_event:
            # Notify subscriber directly with the last event
            asyncio.create_task(listener.callback(self._last_event))
        elif len(self._subscribers) == 1:
            # first subscriber therefore do refresh
            self.request_refresh()

        return listener

    def unsubscribe(self, listener: EventListener[T]) -> None:
        """Unsubscribe from event."""
        self._subscribers.remove(listener)

    def notify(self, event: T) -> bool:
        """Notify subscriber with given event representation."""
        if (not self._notify_on_equal_event) and event == self._last_event:
            _LOGGER.debug("Event is the same! Skipping (%s)", event)
            return False

        self._last_event = event
        if self._subscribers:
            _LOGGER.debug("Notify subscribers with %s", event)
            for subscriber in self._subscribers:
                asyncio.create_task(subscriber.callback(event))
            return True

        _LOGGER.debug("No subscribers... Discharging %s", event)
        return False

    async def _call_refresh_function(self) -> None:
        if self._semaphore.locked():
            _LOGGER.debug("Already refresh function running. Skipping...")
            return

        async with self._semaphore:
            await self._refresh_function()

    def request_refresh(self) -> None:
        """Request manual refresh."""
        if len(self._subscribers) > 0:
            asyncio.create_task(self._call_refresh_function())


class DebounceAtMostEventEmitter(EventEmitter[T]):
    """An event emitter, which debounce the event at most the given time."""

    def __init__(
        self,
        refresh_function: Callable[[], Awaitable[None]],
        debounce_at_most_seconds: int,
    ):
        super().__init__(refresh_function, True)
        self._last_event_time: float = 0.0
        self._debounce_at_most_seconds: Final = debounce_at_most_seconds
        self._timer_task: Optional[asyncio.TimerHandle] = None

    def _call_later(self) -> None:
        self._timer_task = None
        if self._last_event:
            super().notify(self._last_event)

    def notify(self, event: T) -> bool:
        """Notify subscriber with given event representation."""
        self._last_event = event
        if time.time() > self._last_event_time + self._debounce_at_most_seconds:
            notified = super().notify(event)
            if notified:
                self._last_event_time = time.time()
            return notified

        if self._timer_task:
            self._timer_task.cancel()

        self._timer_task = asyncio.get_event_loop().call_later(
            self._debounce_at_most_seconds, self._call_later
        )
        return False


class PollingEventEmitter(EventEmitter[T]):
    """EventEmiter, which is polling data with the given refresh_function on the given interval."""

    def __init__(
        self,
        refresh_interval: int,
        refresh_function: Callable[[], Awaitable[None]],
        status_event: EventEmitter[StatusEvent],
        notify_on_equal_event: bool = False,
    ):
        super().__init__(refresh_function, notify_on_equal_event)
        self._refresh_task: Optional[Task] = None
        self._refresh_interval: int = refresh_interval
        self._status: Optional[VacuumState] = None

        async def on_status(event: StatusEvent) -> None:
            self._status = event.state
            if event.state == VacuumState.STATE_CLEANING:
                self._start_refresh_task()
            else:
                self._stop_refresh_task()

        status_event.subscribe(on_status)

    async def _refresh_interval_task(self) -> None:
        while True:
            await self._call_refresh_function()
            await asyncio.sleep(self._refresh_interval)

    def _start_refresh_task(self) -> None:
        if self._refresh_task is None and len(self._subscribers) != 0:
            self._refresh_task = asyncio.create_task(self._refresh_interval_task())

    def _stop_refresh_task(self) -> None:
        if self._refresh_task is not None:
            task = self._refresh_task
            self._refresh_task = None
            task.cancel()

    def subscribe(self, callback: Callable[[T], Awaitable[None]]) -> EventListener[T]:
        """Subscribe to event."""
        listener = super().subscribe(callback)
        if self._status == VacuumState.STATE_CLEANING:
            self._start_refresh_task()
        return listener

    def unsubscribe(self, listener: EventListener[T]) -> None:
        """Unsubscribe from event."""
        super().unsubscribe(listener)

        if len(self._subscribers) == 0:
            self._stop_refresh_task()
