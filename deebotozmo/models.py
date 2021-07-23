from dataclasses import dataclass
from enum import Enum


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


@dataclass
class Coordinate:
    x: int
    y: int


@dataclass
class Room:
    subtype: str
    id: int
    coordinates: str


class RequestAuth(dict):

    @property
    def user_id(self):
        return self["userid"]

    @property
    def realm(self):
        return self["realm"]

    @property
    def token(self):
        return self["token"]

    @property
    def resource(self):
        return self["resource"]


class VacuumState(Enum):
    STATE_IDLE = 1
    STATE_CLEANING = 2
    STATE_RETURNING = 3
    STATE_DOCKED = 4
    STATE_ERROR = 5
    STATE_PAUSED = 6
