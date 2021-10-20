import inspect

import deebotozmo.events
from deebotozmo.events import EventDto
from deebotozmo.events.const import EVENT_DTO_REFRESH_COMMANDS


def test_events_has_refresh_function():
    for name, obj in inspect.getmembers(deebotozmo.events, inspect.isclass):
        if issubclass(obj, EventDto) and obj != EventDto:
            assert obj in EVENT_DTO_REFRESH_COMMANDS

