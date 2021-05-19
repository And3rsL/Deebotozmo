from dataclasses import dataclass
from typing import List


class Vacuum(dict):
    """Class holds all values, which we get from api. Common values can be accessed through properties."""

    @property
    def company(self):
        return self["company"]

    @property
    def did(self):
        return self["did"]

    @property
    def name(self):
        return self["name"]

    @property
    def nick(self):
        return self["nick"]

    @property
    def resource(self):
        return self["resource"]

    @property
    def device_name(self):
        return self["deviceName"]

    @property
    def status(self):
        return self["status"]

    @property
    def get_class(self):
        return self["class"]


class EventListener:
    """Object that allows event consumers to easily unsubscribe from events."""

    def __init__(self, emitter, callback):
        self._emitter = emitter
        self.callback = callback

    def unsubscribe(self):
        self._emitter.unsubscribe(self)


class EventEmitter:
    """A very simple event emitting system."""

    def __init__(self):
        self._subscribers: List[EventListener] = []

    def subscribe(self, callback) -> EventListener:
        listener = EventListener(self, callback)
        self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener):
        self._subscribers.remove(listener)

    def notify(self, event):
        for subscriber in self._subscribers:
            subscriber.callback(event)


@dataclass
class Coordinate:
    x: int
    y: int


@dataclass
class Room:
    subtype: str
    id: int
    values: str
